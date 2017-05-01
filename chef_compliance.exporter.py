from BaseHTTPServer import BaseHTTPRequestHandler,HTTPServer
from nap.url import Url
import logging
import os, sys
import requests.packages.urllib3
import threading
import time
import operator

requests.packages.urllib3.disable_warnings()

PORT_NUMBER = int(os.environ.get('PORT', 9243))
REFRESH_TOKEN = os.environ.get('REFRESH_TOKEN', '')
API_URL = os.environ.get("API_URL", '')
WAIT_BETWEEN_METRIC_POLL = int(os.environ.get("SLEEP_DURATION", 60))
COMPLIANCE_USERNAME = os.environ.get('COMPLIANCE_USERNAME', "chef_compliance_exporter")
COMPLIANCE_ENVIRONMENT = os.environ.get("COMPLIANCE_ENVIRONMENT", "default")
scans = {}
metrics = []
timestamp = False

if REFRESH_TOKEN == "" or API_URL == "":
    print "Please set REFRESH_TOKEN and API_URL environment variables before you run."
    sys.exit(1)

print "Initialising Chef Compliance Exporter"
print "PORT_NUMBER              : "+str(PORT_NUMBER)
print "REFRESH_TOKEN            : "+REFRESH_TOKEN
print "API_URL                  : "+API_URL
print "WAIT_BETWEEN_METRIC_POLL : "+str(WAIT_BETWEEN_METRIC_POLL)
print "COMPLIANCE_USERNAME      : "+COMPLIANCE_USERNAME
print "COMPLIANCE_ENVIRONMENT   : "+COMPLIANCE_ENVIRONMENT

class chefComplianceExporterHandler(BaseHTTPRequestHandler):

    def set_headers(self, http_code):
        self.send_response(http_code)
        self.send_header('Content-type', 'text/html')
        self.end_headers()

    def do_GET(self):
        if (self.path == "/"):
            self.set_headers(200)
            self.wfile.write("<html>                                \
             <head><title>Chef Compliance Exporter</title></head>   \
             <body>                                                 \
             <h1>Chef Compliance Exporter</h1>                      \
             <p><a href='/metrics'>Metrics</a></p>                  \
             </body>                                                \
             </html>")
        elif (self.path == "/metrics"):
            self.send_response(200)
            self.send_header('Content-type', 'plain/text')
            self.end_headers()
            self.wfile.write("\n".join(metrics)+"\n\n")

        else:
            self.set_headers(404)
            self.wfile.write("<html>                                \
             <head><title>Not found</title></head>                  \
             <body>                                                 \
             <h1>404 - Not Found</h1>                               \
             <p><a href='/metrics'>Metrics</a></p>                  \
             </body>                                                \
             </html>")

class JsonApi(Url):
    def after_request(self, response):
        if response.status_code != 200:
            response.raise_for_status()

        return response.json()

class ChefComplianceServer:
    def __init__(self):
        self.authenticated = False
        self.api_url = API_URL
        self.refresh_token = REFRESH_TOKEN
        self.api_token = False
        self.nodes = []
        self.scans = {}
        self.api = JsonApi(self.api_url)
        self.latest_scan_id = False

    def auth(self):
        print "Generating API Token."
        response = self.api.post('api/login', json={"token": self.refresh_token }, verify=False)
        if u'access_token' in response:
            print "API Token acquired."
            self.api_token = response[u'access_token']

    def get_node_list(self):
        response = self.api.get('api/owners/'+COMPLIANCE_USERNAME+'/envs/'+COMPLIANCE_ENVIRONMENT+'/nodes', headers={ 'Authorization': 'Bearer '+self.api_token }, verify=False)
        for nodeId in response:
            self.nodes.append(nodeId[u'id'])
            self.scans[nodeId[u'id']] = {
                'name': nodeId[u'name'],
                'hostname': nodeId[u'hostname'],
                'lastScan': nodeId[u'lastScan']
            }

    def get_last_scan_id(self, offset):
        response = self.api.get('api/owners/'+COMPLIANCE_USERNAME+'/scans', headers={ 'Authorization': 'Bearer '+self.api_token }, verify=False)
        result_array = sorted(response, key=operator.itemgetter(u'end'), reverse=True)
        if len(result_array) > offset:
            self.latest_scan_id = result_array[(-1)+offset][u'id']
            print "Scan ID : "+self.latest_scan_id
        else:
            print "\n\n\nWARNING: Can not find "+str(len(self.nodes))+" hostnames in the scans.\n"

    def get_metrics(self):
        global scans
        global timestamp

        self.get_node_list()
        offset = 0
        errorOccured = False

        while len(self.nodes) > 0:
            offset += 1
            self.get_last_scan_id(offset)

            if self.latest_scan_id:
                response = self.api.get('api/owners/'+COMPLIANCE_USERNAME+'/scans/'+self.latest_scan_id+'/nodes', headers={ 'Authorization': 'Bearer '+self.api_token }, verify=False)
                for scan in response:
                    if scan[u'node'] in self.nodes:
                        print "=> Found scan summary for "+scan[u'node']
                        self.scans[scan[u'node']][u'patchlevelSummary'] = scan[u'patchlevelSummary']
                        self.scans[scan[u'node']][u'complianceSummary'] = scan[u'complianceSummary']
                        self.nodes.remove(scan[u'node'])
            else:
                self.nodes = []
                errorOccured = True

        if errorOccured is False:
            scans = self.scans

class ThreadHandle (threading.Thread):
        def __init__(self, threadID):
            threading.Thread.__init__(self)
            self.threadID = threadID
        def run(self):
            print "New thread is running "+self.threadID
            if self.threadID == "server":
                init_http_server()
            elif self.threadID == "metrics":
                fetch_metrics()

def format_metrics():
    if len(scans) > 0:
        metrics.append('compliance_scanned_node_count '+str(len(scans)))
        for node in scans:
            metrics.append('compliance_scan_result{hostname="'+scans[node][u'hostname']+'", severity="major"} '+str(scans[node][u'complianceSummary'][u'major']))
            metrics.append('compliance_scan_result{hostname="'+scans[node][u'hostname']+'", severity="skipped"} '+str(scans[node][u'complianceSummary'][u'skipped']))
            metrics.append('compliance_scan_result{hostname="'+scans[node][u'hostname']+'", severity="success"} '+str(scans[node][u'complianceSummary'][u'success']))
            metrics.append('compliance_scan_result{hostname="'+scans[node][u'hostname']+'", severity="critical"} '+str(scans[node][u'complianceSummary'][u'critical']))
            metrics.append('compliance_scan_result{hostname="'+scans[node][u'hostname']+'", severity="total"} '+str(scans[node][u'complianceSummary'][u'total']))
            metrics.append('compliance_scan_result{hostname="'+scans[node][u'hostname']+'", severity="minor"} '+str(scans[node][u'complianceSummary'][u'minor']))

            metrics.append('compliance_scan_patchlevel{hostname="'+scans[node][u'hostname']+'", severity="major"} '+str(scans[node][u'patchlevelSummary'][u'major']))
            metrics.append('compliance_scan_patchlevel{hostname="'+scans[node][u'hostname']+'", severity="success"} '+str(scans[node][u'patchlevelSummary'][u'success']))
            metrics.append('compliance_scan_patchlevel{hostname="'+scans[node][u'hostname']+'", severity="critical"} '+str(scans[node][u'patchlevelSummary'][u'critical']))
            metrics.append('compliance_scan_patchlevel{hostname="'+scans[node][u'hostname']+'", severity="total"} '+str(scans[node][u'patchlevelSummary'][u'total']))
            metrics.append('compliance_scan_patchlevel{hostname="'+scans[node][u'hostname']+'", severity="minor"} '+str(scans[node][u'patchlevelSummary'][u'minor']))

def init_http_server():
    try:
        print 'Starting http server'
        server = HTTPServer(('', PORT_NUMBER), chefComplianceExporterHandler)
        print 'Started http server on port ' , PORT_NUMBER
    except KeyboardInterrupt:
        print '^C received, shutting down the web server'
        server.socket.close()
        sys.exit(0)

    server.serve_forever()

def fetch_metrics():
    print "Fetching metrics"
    chefServer = ChefComplianceServer()
    chefServer.auth()
    chefServer.get_metrics()
    format_metrics()

if __name__ == '__main__':
    fetch_metrics()
    serverThread = ThreadHandle("server")
    serverThread.start()

    while ( True ):
        metricThread = ThreadHandle("metrics")
        metricThread.start()
        time.sleep(.1)
        while( metricThread.isAlive() ):
            time.sleep(WAIT_BETWEEN_METRIC_POLL)
