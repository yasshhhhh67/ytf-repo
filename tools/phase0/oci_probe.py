"""Read-only OCI probe: tenancy, ADs, existing instances, A1 limits/usage, subnets, Ubuntu arm64 images."""
import configparser, io, json, subprocess, sys
import oci

def cred(name):
    return subprocess.run(['systemd-creds', 'decrypt', f'--name={name}', f'/etc/credstore.encrypted/{name}', '-'],
                          capture_output=True, check=True).stdout.decode()

cp = configparser.ConfigParser(); cp.read_string(cred('ytf.oci-config'))
d = cp['DEFAULT']
cfg = {'user': d['user'], 'fingerprint': d['fingerprint'], 'tenancy': d['tenancy'], 'region': d['region'],
       'key_content': cred('ytf.oci-api-key')}
oci.config.validate_config(cfg)
T = cfg['tenancy']
idn = oci.identity.IdentityClient(cfg); comp = oci.core.ComputeClient(cfg); net = oci.core.VirtualNetworkClient(cfg)
lim = oci.limits.LimitsClient(cfg)
out = {'region': cfg['region'], 'home_region': [r.region_name for r in idn.list_region_subscriptions(T).data if r.is_home_region]}
ads = [a.name for a in idn.list_availability_domains(T).data]; out['ads'] = ads
comps = [T] + [c.id for c in oci.pagination.list_call_get_all_results(idn.list_compartments, T, compartment_id_in_subtree=True).data if c.lifecycle_state == 'ACTIVE']
inst = []
for c in comps:
    for i in comp.list_instances(c).data:
        if i.lifecycle_state != 'TERMINATED':
            inst.append({'name': i.display_name, 'shape': i.shape, 'state': i.lifecycle_state, 'ad': i.availability_domain,
                         'ocpus': getattr(i.shape_config, 'ocpus', None), 'mem': getattr(i.shape_config, 'memory_in_gbs', None)})
out['instances'] = inst
a1 = {}
for name in ['standard-a1-core-count', 'standard-a1-memory-count']:
    for ad in ads:
        try:
            v = lim.get_resource_availability('compute', name, T, availability_domain=ad).data
            a1[f'{name}@{ad[-4:]}'] = {'used': v.used, 'available': v.available}
        except Exception as e:
            a1[f'{name}@{ad[-4:]}'] = str(e)[:80]
out['a1_limits'] = a1
subs = []
for c in comps:
    for s in net.list_subnets(c).data:
        subs.append({'name': s.display_name, 'id': s.id, 'cidr': s.cidr_block, 'public': not s.prohibit_public_ip_on_vnic})
out['subnets'] = subs
imgs = comp.list_images(T, operating_system='Canonical Ubuntu', shape='VM.Standard.A1.Flex', sort_by='TIMECREATED').data
out['ubuntu_a1_images'] = [i.display_name for i in imgs[:4]]
print(json.dumps(out, indent=1))
