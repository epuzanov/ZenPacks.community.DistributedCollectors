========================================
ZenPacks.community.DistributedCollectors
========================================

About
=====

This ZenPack provides UI for configuring multiple collectors with Zenoss Core.
It implement remote collector configuration method described in `How to install 
distributed collectors <http://community.zenoss.org/docs/DOC-2496>`_ manual.

Requirements
============

Zenoss
------

You must first have, or install, Zenoss 2.5.2 or later. This ZenPack was tested
against Zenoss 2.5.2, Zenoss 3.2 and Zenoss 4.2.0. You can download the free
Core version of Zenoss from http://community.zenoss.org/community/download.

Installation
============

Install ZenPack on master server
--------------------------------

Download the `Distributed Collectors ZenPack <http://community.zenoss.org/docs/DOC-5861>`_.
Copy this file to your Zenoss server and run the following commands as the zenoss
user.

    ::

        zenpack --install ZenPacks.community.DistributedCollectors-2.0.1.egg
        zenoss restart

Note that Developer Installation (with --link option) of ZenPacks not supported.

Install remote collector
------------------------

install Zenoss on remote collector without any ZenPacks


Configure "ssh public key authentication"
-----------------------------------------

on remote collector server check if /home/zenoss/.ssh directory exists, if not,
than run **ssh-keygen** as **zenoss** user.

on Zenoss master server run as **zenoss** user:

    ::

        ssh-keygen -t rsa
        cat ~/.ssh/id_rsa.pub | ssh zenoss@remote_collector_name "cat - >> ~/.ssh/authorized_keys"


Usage
=====

Add Remote Collector
-----------------------

in "Collectors" -> select menu item "Add Remote Monitor..." and enter name or ip
address of remote collector.

Update Remote Collectors
--------------------------

update your repote collector after installing, updating or romoving of any
ZenPacks.

#. in "Collectors" select all remote collectors you want update.
#. in "Collectors" -> select menu item "Update Remote Monitors..."

Delete Remote Collectors
--------------------------

#. in "Collectors" select all remote collectors you want update.
#. in "Collectors" -> select menu item "Delete Remote Monitors..."
