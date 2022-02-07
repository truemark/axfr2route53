# axfr2route53.py

This script imports DNS records from a zone file and UPSERTS them into a
Route53 hosted zone.

This tool is intended for DNS migrations from any provider migrating into
AWS Route53.

Note: current support is for zone file import only. Plan to add direct AXFR
import.

To import A records from filename for the example.com domain:
```shell
./axfr2route53.py -f filename.zone -d example.com -z Z1234567891011 -t A
```

Supported record types:
 - A
 - AAAA
 - CNAME
 - MX
 - NS (ignored for @ records)
 - PTR
 - SPF
 - SRV
 - TXT

## Plans
Add support for direct AXFR import.
Add support for special `-t` type ALL for full import
Add support for dry-run or diff changes output
