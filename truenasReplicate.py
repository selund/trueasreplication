#!/usr/bin/python3

import requests, json, subprocess, shlex, sys, time, pprint, urllib3

#Source and target are tow dicts in a list in a json file containing auth and addresses. 
#source = {'hostname':'<hostname>','auth':'Bearer  <api token from truenas>'}
#target = {'hostname':'<hoarname>','auth':'Bearer  <api token from truenas>','ipmi':'<ipmi ip>','ipmi_pw':'<ipmi password>'}

source,target=json.load(open('config.json','r'))

payload = {}
Debug = True
runningRepl=1
start = time.time()

urllib3.disable_warnings()

def debug(txt):
    if Debug:
        print(txt)
    else:
        pass

def getPool(host):
    baseUrl = "https://%s/api/v2.0/" % host['hostname']
    headers = { 'Authorization': host['auth'] }
    replUrl = "%s/pool/" % baseUrl
    response = requests.request("GET", replUrl, headers=headers, data=payload,verify=False)
    return response.json()

def getReplications(host):
    baseUrl = "https://%s/api/v2.0/" % host['hostname']
    headers = { 'Authorization': host['auth'] }
    replUrl = "%s/replication/" % baseUrl
    response = requests.request("GET", replUrl, headers=headers, data=payload,verify=False)
    return response.json()

def startRepl(host):
    runningRepl=0
    baseUrl = "https://%s/api/v2.0/" % host['hostname']
    headers = { 'Authorization': host['auth'] }
    replications = getReplications(host)
    runninRepl=0
    #Check and start replicatins that needs to be started
    for replication in replications:
        replId = replication['id']
        replUrl = "%sreplication/id/%s/run" % (baseUrl,replId)
        #A replication can fail, and have a job, or it can succeed and the job is removed, henc the two check
        if replication['job']:
            if replication['job']['state'] == "SUCCESS":
                debug("replication already done for %s" % replId)
            elif replication['state']['state'] == 'RUNNING':
                runningRepl+=1
                debug("replication already running")
            elif replication['job']['state'] == 'FAILED':
                response = requests.request("POST", replUrl, headers=headers, data=payload,verify=False)
                runningRepl+=1
                debug("Tryng to start with state %s" % replication['job']['state'])
                debug(response)
                # wait 5 seconds to start a new job. Starting a new job to soon seems to cause issues
                time.sleep(5)
                
        else:
            if replication['state']['state'] == 'ERROR':
                response = requests.request("POST", replUrl, headers=headers, data=payload,verify=False)
                runningRepl+=1
                debug("Tryng to start with state %s" % replication['state']['state'])
                debug(response)
            elif replication['state']['state'] == 'FINISHED':
                debug("Replication already done for %s" % replId)
            else:
                debug("%s replid is in an unknown state " % replId)
    #Return the number of currently running replications 
    return runningRepl

def startTarget(host):
    #Check current status
    cmd = 'ipmitool -H %s -U Power -P %s power status' % (host['ipmi'],host['ipmi_pw'])
    ret = subprocess.getoutput(cmd)
    if ret == "Chassis Power is off": 
        debug('Power is off, turning on')
        cmd = 'ipmitool -H %s -U Power -P %s power on' % (host['ipmi'],host['ipmi_pw'])
        ret = subprocess.getoutput(cmd)
        return True
    elif ret == "Chassis Power is on":
        debug('Power already on')
        return True
    else:
        debug('Power is unknown')
        return False

def shutdownTarget(host):
    #Check current status
    cmd = 'ipmitool -H %s -U Power -P %s power status' % (host['ipmi'],host['ipmi_pw'])
    ret = subprocess.getoutput(cmd)
    if ret == "Chassis Power is on": 
        debug('Power is on, turning off soft')
        cmd = 'ipmitool -H %s -U Power -P %s power soft' % (host['ipmi'],host['ipmi_pw'])
        ret = subprocess.getoutput(cmd)
        return True
    elif ret == "Chassis Power is off":
        debug('Power already off')
        return True
    else:
        debug('Power is unknown')
        return False

def checkDatapoolUp(host):
    for i in range(10):
        pool = getPool(host)
        #checking if datapool is up
        if pool[0]['name'] == 'datapool':
            return True 
        else:
            #Wait 30 seconds and try again upto 10 times
            time.sleep(30)
    return False

def shutdownTruenas(host):
    baseUrl = "https://%s/api/v2.0/" % host['hostname']
    headers = { 'Authorization': host['auth'] }
    systemUrl = "%s/system/shutdown" % baseUrl
    response = requests.request("POST", systemUrl, headers=headers, data=payload,verify=False)
    return response.json()

if startTarget(target):
    debug("Powering on or already on")
    pass
else:
    debug("Unable to power on system")
    debug("Total time: %i " % (time.time()-start))
    sys.exit(1)
#Using for loop for sleep to log at 10 seconds interval
for x in range(10):
    debug("Sleeping for %i more seconds" % (300-x*30))
    time.sleep(30)
if checkDatapoolUp(target):
    debug("Datapool is up on target")
    pass
else:
    debug("Pools not online on target")
    debug("Total time: %i " % (time.time()-start))
    sys.exit(1) 
if checkDatapoolUp(target):
    debug("Datapool is up on source")
    pass
else:
    debug("Pools not online on source")
    debug("Total time: %i " % (time.time()-start))
    sys.exit(1) 
while runningRepl != 0:
    runningRepl = startRepl(source)
    debug("Stilll %s replications running" % runningRepl)
    time.sleep(30)
ret = shutdownTruenas(target)
#Using for loop for sleep to log at 10 seconds interval
for x in range(10):
    debug("Sleeping for %i more seconds" % (300-x*30))
    time.sleep(30)
debug("Replication complete")
ret = shutdownTarget(target)
if ret:
    debug("Shutdown of target done")
    debug("Total time: %i " % (time.time()-start))
    sys.exit(0)
else:
    debug("Shutdown of target failed")
    debug("Total time: %i " % (time.time()-start))
    sys.exit(1)
