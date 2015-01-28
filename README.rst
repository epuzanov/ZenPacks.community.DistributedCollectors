========================================
ZenPacks.community.DistributedCollectors
========================================

About
=====

This ZenPack provides a UI for configuring multiple collectors with Zenoss Core.
It implements remote collector configuration using the method described in `How to install
distributed collectors <http://community.zenoss.org/docs/DOC-2496>`_ manual.

Requirements
============

Zenoss
------

You must first have, or install, Zenoss 2.5.2 or later. This ZenPack was tested
against Zenoss 2.5.2, Zenoss 3.2, 4.2.0 and Zenoss 4.2.5. You can download the free
Core version of Zenoss from http://community.zenoss.org/community/download.

Installation
============

Install ZenPack on the master server
--------------------------------

Download the `Distributed Collectors ZenPack <http://wiki.zenoss.org/ZenPack:Distributed_Collector_%28Open_Source%29>`_.
Copy this file to your Zenoss server and run the following commands as the zenoss
user.

    ::

        zenpack --install ZenPacks.community.DistributedCollectors-2.0.2.egg
        zenoss restart

Note that Developer Installation (with --link option) of ZenPacks not supported - all ZenPacks including this one must be in the normal directories to be synchronised to the collectors.

Install remote collector
------------------------

Install Zenoss on remote collector without any ZenPacks - you may have to delete any entries from the /opt/zenoss/var/zenpack_actions.txt file first.


Configure "ssh public key authentication"
-----------------------------------------

On the remote collector server check if /home/zenoss/.ssh directory exists, if not,
than run **ssh-keygen** as **zenoss** user.

on Zenoss master server run as **zenoss** user:

    ::

        ssh-keygen -t rsa
        cat ~/.ssh/id_rsa.pub | ssh zenoss@remote_collector_name "cat - >> ~/.ssh/authorized_keys"

Test you can ssh zenoss@remote_collector_name without prompts coming up for "add to known hosts". If it fails then check the files are all chmod 600 in the .ssh directory on both systems.


Usage
=====

Add Remote Collector
-----------------------

In "Collectors" -> select menu item "Add Remote Monitor..." and enter name or ip
address of remote collector. This must be the same name, fully qualified domain name or ip as you have tested with ssh or the local UserKnownHostsFile will not work.

Update Remote Collectors
--------------------------

Update your remote collector after installing, updating or removing any ZenPacks.

#. in "Collectors" select all remote collectors you want update.
#. in "Collectors" -> select menu item "Update Remote Monitors..."

Delete Remote Collectors
--------------------------

#. in "Collectors" select all remote collectors you want update.
#. in "Collectors" -> select menu item "Delete Remote Monitors..."


Zenoss Graph Rendering
-------------------------
The RRD files and rendering of graph images occurs on the remote collector - to use the zenbub connection and Zenoss Web Proxy rather than requiring users to connect to both systems then:

Navigate to Advanced > Collectors > [collectorname] > Edit > RenderURL to proxy through the main hub

from
        http://collectorname.domain.com:8091
to
        http://hubname.domain.com:8090/collectorname.domain.com

    MAKE SURE NOT TO CHANGE RENDER USER OR PASSWORD (autofill will try to when using Firefox or Chrome)

Dynamic thresholds on memory from Zenpacks that expect access to RRD files such as
    (here.getRRDValue('memTotalSwap') or 3145724) * .80
will fail since the hub cannot access the RRD file. Use this instead
    ((here.os.totalSwap/1024) or 3145724) * .80


Firewalls
----------
On the remote collector add port 8091:tcp

        lokkit -v --port=8091:tcp #Zenoss graph RRD render

On the main zenoss hub then add the following ports:

    ::
        
        lokkit -v --port=8090:tcp #Zenoss Web Proxy connection (remote connector proxy to RRD render graphs)
        lokkit -v --port=8100:tcp #ZeoDB
        lokkit -v --port=3306:tcp #mysql
        lokkit -v --port=8789:tcp #zenhub


