#!/usr/bin/env python3
import argparse

'''
This script allows transfer of DNS from an upstream DNS server via AXFR as
defined in RFC 5936 and submits entries to Route 53 via boto3. It uses the
UPSERT action to either create a record or update the existing one. You can
use it to do a one time transfer of a type of record from the zone you need or
perform a continual sync of DNS from an upstream server.

It is safe to run this more than once.

The upstream DNS server must be set to allow AXFR requests.  You can test this
by performing: `dig AXFR example.com @1.2.3.4`

**Examples**

Transfer A records via AXFR from -s 1.2.3.4 DNS server.
Usage: `./AXFR2Route53.py -s 1.2.3.4 -d example.com -z Z1234567891011 -t A`

Transfer CNAME records via -f zone file import
Usage: `./AXFR2Route53.py -f filename -d example.com -z Z1234567891011 -t CNAME`
'''


try:
    import boto3
except ImportError:
    raise SystemExit("Requires boto3: pip install boto3")
try:
    from dns import zone as dnszone
    #from dns import query
    from dns.rdataclass import *
    from dns.rdatatype import *
    from dns.exception import DNSException
except ImportError:
    raise SystemExit("Requires dnspython: pip install dnspython")


class AXFR2Route53(object):
    ''' Update Route53 with entries from upstream DNS Server. '''
    def __init__(self, options):
        self.options = options
        self.update_records()

    def update_records(self):
        ''' Run route53 updates based on AXFR request '''

        _filename = self.options.filename
        _domain = self.options.domain
        _hostedzone = self.options.hostedzone
        _recordtype = self.options.recordtype

        ## commented this AXFR block while working on file import
        ## will need to be extended to support either option
        #try:
        #    print("Making AXFR request to " + self.options.dns_server + "...")
        #except TypeError:
        #    raise SystemExit("No DNS server set. try again with -s to set the "
        #                     "server to make the AXFR request against.")

        try:
            print()
            print("Importing zone from file: {}".format(_filename))
        except TypeError:
            raise SystemExit("No filename defined. Use -f to define the path to the zone file.")

        try:
            z = dnszone.from_file(_filename, _domain)
        except AttributeError:
            raise SystemExit("No domain defined. Use -d to define the domain to transfer.")

        if _hostedzone is None:
            raise SystemExit("No Hosted Zone ID provided. Try again with -z.")

        dns_changes = []
        adict = {}
        print("Processing {} records for {}...".format(str(_recordtype), str(_domain)))
        print()

        if len(z.nodes) == 0:
            raise SystemExit("No records found to process.\n")

        print("Total records downloaded: " + str(len(z.nodes)))

        ## standard record types
        if _recordtype == "A":
            rdtypevar = A
            rdclassvar = IN
        elif _recordtype == "AAAA":
            rdtypevar = AAAA
            rdclassvar = IN
        elif _recordtype == "CNAME":
            rdtypevar = CNAME
            rdclassvar = IN
        elif _recordtype == "MX":
            rdtypevar = MX
            rdclassvar = IN
        elif _recordtype == "NS":
            rdtypevar = NS
            rdclassvar = IN
        elif _recordtype == "PTR":
            rdtypevar = PTR
            rdclassvar = IN
        elif _recordtype == "SPF":
            rdtypevar = SPF
            rdclassvar = IN
        elif _recordtype == "TXT":
            rdtypevar = TXT
            rdclassvar = IN
        elif _recordtype == "SRV":
            rdtypevar = SRV
            rdclassvar = IN
        else:
            raise SystemExit("Unknown or unsupported record type in Route 53: ".format(_recordtype))

        ## parse records and build dictionary
        for name, node in z.nodes.items():
            rdataset = None
            rdataset = node.get_rdataset(
                rdclass=rdclassvar, rdtype=rdtypevar)
            if not rdataset:
                continue
            for rds in rdataset:
                ## we don't want to clobber Route53 NS records
                ## as we're replacing those NS for Route53
                if str(name) == "@" and _recordtype == 'NS':
                    print("Skipping NS record @")
                    continue
                ## build dictionary of records
                if str(name) == "@":
                    recordname = _domain + "."
                    if recordname in adict:
                        ipaddr = str(rds)
                        adict[recordname]['records'].append(ipaddr)
                    else:
                        ipaddr = str(rds)
                        adict[recordname] = {'records': [ipaddr]}
                        adict[recordname].update({'ttl': str(rdataset.ttl)})
                else:
                    recordname = str(name) + "." + _domain + "."
                    if recordname in adict:
                        ipaddr = str(rds)
                        adict[recordname]['records'].append(ipaddr)
                    else:
                        ipaddr = str(rds)
                        adict[recordname] = {'records': [ipaddr]}
                        adict[recordname].update({'ttl': str(rdataset.ttl)})

        ## process the changes
        for key, thedict in adict.items():
            ResourceRecordList = []
            for record in thedict['records']:
                ResourceRecordList.append({'Value': record})
            dns_changes.append({'Action': 'UPSERT',
                                'ResourceRecordSet': {
                                    'Name': key,
                                    'Type': _recordtype,
                                    'TTL': int(thedict['ttl']),
                                    'ResourceRecords': ResourceRecordList
                                    }
                                })
        if len(dns_changes) == 0:
            raise SystemExit("No " + _recordtype + " records found.")

        print("Total records processed: " + str(len(dns_changes)))

        # connecting to route53 via boto
        print("Connecting to Route53...")

        ## submit changes to route53 in batches
        client = boto3.client('route53')
        if len(dns_changes) > 98:
            print("Batching required...")
            chunks = [dns_changes[x:x+98] for x in range(0, len(dns_changes), 98)]
            chunkcount = 0
            for chunk in chunks:
                chunkcount = chunkcount + 1
                client.change_resource_record_sets(
                    HostedZoneId=str(_hostedzone),
                    ChangeBatch={'Changes': chunk})
                print("Batch " + str(chunkcount) + " submitted to Route53")
        else:
            client.change_resource_record_sets(
                HostedZoneId=str(_hostedzone),
                ChangeBatch={'Changes': dns_changes})
            print("Changes submitted to Route53")
            print()


def parser_setup():
    ''' Setup the options parser '''
    desc = 'Import zone file resource records and submit to Route53 zoneID.'
    parser = argparse.ArgumentParser(description=desc)
    parser.add_argument('-d',
                        action='store',
                        dest='domain',
                        help='Domain to submit AXFR request for')
    #parser.add_argument('-s',
    #                    action='store',
    #                    dest='dns_server',
    #                    help='DNS server to send AXFR request to. '
    #                         'FQDN is allowed. This ia required.')
    parser.add_argument('-t',
                        action='store',
                        dest='recordtype',
                        default='A',
                        help='Record type to process.')
    parser.add_argument('-f',
                        action='store',
                        dest='filename',
                        help='Import zone from file path.')
    parser.add_argument('-c',
                        action='store',
                        dest='comment',
                        default='Managed by AXFR2Route53.py',
                        help='Set Route53 record comment.')
    parser.add_argument('-z',
                        action='store',
                        dest='hostedzone',
                        help='Hosted zone to submit records to. '
                             'This is required.')
    return parser


def main():
    ''' Setup options and call main program '''
    parser = parser_setup()
    options = parser.parse_args()
    AXFR2Route53(options)


if __name__ == '__main__':
    main()
