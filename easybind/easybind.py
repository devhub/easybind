import dns, os, os.path, re
from dns.rdtypes.ANY.SOA import SOA
from easyzone.easyzone import Zone as EasyZone

CONF_FILENAME = '/etc/bind/named.conf.local'
NAMESERVERS = []
ZONE_FILENAME = '/etc/bind/zones/{domain}.hosts'
ZONE_REGEX_STR = r'^zone "%s" \{.*?\s+type (.*?);\s+file ".*?";\s+\};\s*'
ZONE_REGEX = re.compile(ZONE_REGEX_STR % '(.*)', re.MULTILINE)
ZONE_TEMPLATE = '''\
zone "%(domain)s" {
    type %(zone_type)s;
    file "%(zone_filename)s";
};
'''


class Zone(EasyZone):

    def __init__(self, domain):
        super(Zone, self).__init__(domain)

        if os.path.isfile(self.template_filename):
            self.load_from_file(self.template_filename)
        else:
            rname = 'info.%s' % domain
            dns_name = dns.name.from_text(self.domain)
            self._zone = dns.zone.Zone(dns_name)
            self.add_name(dns_name)
            self._zone.origin = dns_name
            root = self.root
            root_node = self._zone[dns_name]
            root.soa = root_node.get_rdataset(dns.rdataclass.IN,
                                              dns.rdatatype.SOA, create=True)
            root.soa.add(SOA(dns.rdataclass.IN, dns.rdatatype.SOA,
                             dns.name.from_text(NAMESERVERS[0]), # mname
                             dns.name.from_text(rname), # rname
                             2000010100, # serial
                             10800, # refresh
                             3600, # retry
                             604800, # expire
                             38400)) # minimum
            for ns in NAMESERVERS:
                records = self.root.records('NS', create=True)
                records.add('%s.' % ns)
            self.dns_name = dns_name

    @property
    def template_filename(self):
        'Location of the zone file using ZONE_TEMPLATE'
        return ZONE_FILENAME.replace('{domain}', self.domain.strip('.'))

    def delete(self, update_conf=False):
        'Delete the zone file'
        os.remove(self.template_filename)
        if update_conf and self.in_conf(): # remove entry in named.conf
            content = open(CONF_FILENAME).read()
            quoted_domain = self.domain[:-1].replace('.', '\.')
            repl_regex = re.compile(ZONE_REGEX_STR % quoted_domain,
                re.MULTILINE)
            new_content = re.sub(repl_regex, '', content,
                re.MULTILINE)
            if content != new_content:
                out = open(CONF_FILENAME, 'w')
                out.write(new_content)
                out.close()

    def in_conf(self):
        'Check if record exists within the named.conf file'
        content = open(CONF_FILENAME).read()
        zones = [z.group(1) for z in ZONE_REGEX.finditer(content)]
        if self.domain.strip('.') in zones:
            return True
        else:
            return False

    def name(self, subdomain=None):
        'Lazy retrieval of Name object from self.names'
        if not subdomain: # return root if subdomain not specified
            return self.root

        with_domain = '%s.%s' % (subdomain, self.domain)
        if subdomain not in self.names and with_domain not in self.names:
            self.add_name(with_domain)
        if subdomain in self.names:
            return self.names[subdomain]
        else:
            return self.names[with_domain]

    def save(self, autoserial=True, update_conf=True):
        super(Zone, self).save(self.template_filename, autoserial)
        if update_conf and not self.in_conf(): # add entry to named.conf
            content = open(CONF_FILENAME).read()
            content += ZONE_TEMPLATE % {
                'domain': self.domain[:-1],
                'zone_filename': self.template_filename,
                'zone_type': 'master',
            }
            out = open(CONF_FILENAME, 'w')
            out.write(content)
            out.close()

    def __repr__(self):
        return 'Zone(domain=%s)' % self.domain
