#!/usr/bin/env python

'''
DigitalOcean external inventory script
=================================

Generates inventory that Ansible can understand by making API request to
DigitalOcean using the python-digitalocean library.

This script assumes Ansible is being executed where the following
environment have already been set:
    export DIGITALOCEAN_CLIENT_ID='DO123'
    export DIGITALOCEAN_API_KEY='abc123'

Alternative, they can be passed on the command-line with --client-id and --api-key.

When run against a specific droplet host, returns informaiton about that droplet.

'''

# (c) 2013, Evan Wies <evan@neomantra.net>
#
# Adapted from the EC2 inventory plugin:
# https://github.com/ansible/ansible/blob/devel/plugins/inventory/ec2.py
#
# This file is part of Ansible,
#
# Ansible is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Ansible is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Ansible.  If not, see <http://www.gnu.org/licenses/>.

######################################################################

import os
import sys
import argparse
from time import time

try:
    import json
except ImportError:
    import simplejson as json

try:
    import requests
except ImportError:
    print "failed=True msg='requests library required for this module'"
    sys.exit(1)



class DigitalOceanInventory(object):
    def __init__(self):
        ''' Main execution path '''

        # Inventory of droplets, grouped by droplets, regions, images, ssh_keys, 
        # sizes, domains
        self.inventory = {}

        # Index of hostname (address) to droplet ID
        self.index = {}

        # Read settings and parse CLI arguments
        #TODO self.read_settings()
        self.parse_cli_args()

        # Setup credentials
        self.client_id = self.args.client_id or os.getenv("DIGITALOCEAN_CLIENT_ID")
        self.api_key = self.args.api_key or os.getenv("DIGITALOCEAN_API_KEY")

        # Setup cache
        cache_path = self.args.cache_path or os.getenv("DIGITALOCEAN_CACHE_PATH") or '.'
        self.cache_path_cache = cache_path + "/ansible-digitalocean.cache"
        self.cache_path_index = cache_path + "/ansible-digitalocean.index"
        self.cache_max_age = self.args.cache_max_age or os.getenv("DIGITALOCEAN_CACHE_MAX_AGE") or 0

        # Check cache
        if self.args.refresh_cache:
            self.do_api_calls_update_cache()
        elif not self.is_cache_valid():
            self.do_api_calls_update_cache()

        # Data to print
        if self.args.host:
            data_to_print = self.json_format_dict(self.get_host_info(), True)

        elif self.args.list:
            # Display list of droplets for inventory
            if len(self.inventory) == 0:
                data_to_print = self.get_inventory_from_cache()
            else:
                data_to_print = self.json_format_dict(self.inventory, True)

        print data_to_print


    def __do_api(self, path, params=dict()):
        request = { 'client_id': self.client_id, 'api_key': self.api_key }
        request.update(params)
        response = requests.get("https://api.digitalocean.com/%s" % path, params=request)
        data = response.json()
        if data['status'] != "OK":
            raise Exception(data)
        return data


    def is_cache_valid(self):
        ''' Determines if the cache files have expired, or if it is still valid '''

        if os.path.isfile(self.cache_path_cache):
            mod_time = os.path.getmtime(self.cache_path_cache)
            current_time = time()
            if (mod_time + self.cache_max_age) > current_time:
                if os.path.isfile(self.cache_path_index):
                    return True

        return False


    def parse_cli_args(self):
        ''' Command line argument processing '''

        parser = argparse.ArgumentParser(description='Produce an Ansible Inventory file based on DigitalOcean')
        parser.add_argument('--list', action='store_true', default=True,
                           help='List droplets (default: True)')
        parser.add_argument('--host', action='store',
                           help='Get all the variables about a specific droplet')

        parser.add_argument('--cache-path', action='store',
                           help='Path to the cache files (default: .)')
        parser.add_argument('--cache-max_age', action='store',
                           help='Maximum age of the cached items (default: 0)')
        parser.add_argument('--refresh-cache', action='store_true', default=False,
                           help='Force refresh of cache by making API requests to DigitalOcean (default: False - use cache files)')

        parser.add_argument('--client-id', action='store',
                           help='DigitalOcean Client ID')
        parser.add_argument('--api-key', action='store',
                           help='DigitalOcean API Key')

        self.args = parser.parse_args()


    def do_api_calls_update_cache(self):
        ''' Do API calls to get the droplets, and save data in cache files '''

        regions = dict()
        for region in self.__do_api('/regions')['regions']:
            regions[ region['id'] ] = region['slug'] or region['id']

        droplets = self.__do_api('/droplets')['droplets']
        for droplet in droplets:
            region_name = regions.get( droplet['region_id'], 'Unknown Region' )
            self.add_droplet( droplet, region_name )

        self.write_to_cache(self.inventory, self.cache_path_cache)
        self.write_to_cache(self.index, self.cache_path_index)


    def get_droplet(self, droplet_id):
        '''Get details about a specific droplet '''
        return self.__do_api('/droplets/'+str(droplet_id))['droplet']


    def add_droplet(self, droplet, region_name):
        ''' Adds a droplet to the inventory and index, as long as it is addressable'''

        dest = droplet['ip_address']
        if not dest:
            # Skip droplets we cannot address (when would this be on DigitalOcean?)
            return

        # Add to index
        self.index[dest] = [ droplet['region_id'], droplet['id'] ]

        # Inventory: Group by instance ID (always a group of 1)
        self.inventory[ droplet['id'] ] = [dest]

        # Inventory: Group by region
        self.push( self.inventory, region_name, dest )  

        # Inventory: Group by name
        self.push( self.inventory, droplet['name'], dest )  


    def get_host_info(self):
        ''' Get variables about a specific host '''

        if len(self.index) == 0:
            # Need to load index from cache
            self.load_index_from_cache()

        if not self.args.host in self.index:
            # try updating the cache
            self.do_api_calls_update_cache()
            if not self.args.host in self.index:
                # host migh not exist anymore
                return self.json_format_dict({}, True)

        (region, droplet_id) = self.index[self.args.host]

        instance = self.get_droplet(droplet_id)
        return instance


    def push(self, my_dict, key, element):
        ''' Pushed an element onto an array that may not have been defined in
        the dict '''

        if key in my_dict:
            my_dict[key].append(element);
        else:
            my_dict[key] = [element]


    def get_inventory_from_cache(self):
        ''' Reads the inventory from the cache file and returns it as a JSON
        object '''

        cache = open(self.cache_path_cache, 'r')
        json_inventory = cache.read()
        return json_inventory


    def load_index_from_cache(self):
        ''' Reads the index from the cache file sets self.index '''

        cache = open(self.cache_path_index, 'r')
        json_index = cache.read()
        self.index = json.loads(json_index)


    def write_to_cache(self, data, filename):
        ''' Writes data in JSON format to a file '''

        json_data = self.json_format_dict(data, True)
        cache = open(filename, 'w')
        cache.write(json_data)
        cache.close()


    def to_safe(self, word):
        ''' Converts 'bad' characters in a string to underscores so they can be
        used as Ansible groups '''

        return re.sub("[^A-Za-z0-9\-]", "_", word)


    def json_format_dict(self, data, pretty=False):
        ''' Converts a dict to a JSON object and dumps it as a formatted
        string '''

        if pretty:
            return json.dumps(data, sort_keys=True, indent=2)
        else:
            return json.dumps(data)


# Run the script
DigitalOceanInventory()





