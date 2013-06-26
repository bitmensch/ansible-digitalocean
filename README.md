# Ansible module for DigitalOcean

## Overview

This is an [Ansible](http://www.ansibleworks.com/) module for working with [DigitalOcean](https://www.digitalocean.com/).

Currently there's just an inventory script.  That still needs work with respect to how it groups things.

Eventually, I want to be able to fully manage droplets with this.

## Installation

This module requires the [Python Requests library](http://python-requests.org/); here are [installation instructions](http://docs.python-requests.org/en/latest/user/install.html "Install Requests").  On Ubuntu/Debian, you can run `sudo apt-get install python-requests`.

## Configuration

The `ansible-digitalocean` modules takes a configuration file named `digitalocean.ini` which must be in the same directory as the file `digitalocean_inventory.py`.  The repo has an [example file](digitalocean.ini "Default digitalocean.ini file").  It has the following configuration parameters:

  * `client_id`: your DigitalOcean Client ID

  * `api_key`: your DigitalOcean API Key

  * `cache_path` and `cache_max_age`: *TODO:* are we keeping the cache?

## Usage

You need to supply your [DigitalOcean credentials](https://www.digitalocean.com/api_access) to the module.   You can do this one of three ways:

 * in your `digitalocean.ini` file, as described in the [Configuration section](#Configuration)

 * the environment variables `DIGITALOCEAN_CLIENT_ID` and `DIGITALOCEAN_API_KEY`
```
    export DIGITALOCEAN_CLIENT_ID='DO123'
    export DIGITALOCEAN_API_KEY='abc123'
```
 * on the command-line with `--client-id` and `--api-key`
```
digitalocean_inventory.py --client-id=DO123 --api-key=abc123
```

## Warning

I'm an Ansible n00b.  Hopefully that will change with time....
