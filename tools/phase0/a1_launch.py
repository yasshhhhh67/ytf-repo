"""Try to create the Always Free A1 render worker (2 OCPU / 12 GB / 50 GB boot). Idempotent.
Exit codes: 0 = exists or created, 3 = out of capacity (retry later), 1 = other error.
Never creates anything beyond Always Free limits: checks A1 availability first."""
import configparser, json, os, subprocess, sys, time
import oci

NAME = 'ytf-worker-a1'; OCPUS = 2; MEM = 12; BOOT_GB = 50

def cred(n):
    cd = os.environ.get('CREDENTIALS_DIRECTORY')       # set by systemd LoadCredentialEncrypted=
    if cd:
        return open(os.path.join(cd, n)).read()
    return subprocess.run(['systemd-creds', 'decrypt', f'--name={n}', f'/etc/credstore.encrypted/{n}', '-'],
                          capture_output=True, check=True).stdout.decode()

def log(**kw):
    print(json.dumps({'ts': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), **kw}), flush=True)

cp = configparser.ConfigParser(); cp.read_string(cred('ytf.oci-config')); d = cp['DEFAULT']
cfg = {'user': d['user'], 'fingerprint': d['fingerprint'], 'tenancy': d['tenancy'], 'region': d['region'], 'key_content': cred('ytf.oci-api-key')}
T = cfg['tenancy']
idn, comp, net, lim = (oci.identity.IdentityClient(cfg), oci.core.ComputeClient(cfg), oci.core.VirtualNetworkClient(cfg), oci.limits.LimitsClient(cfg))

for i in comp.list_instances(T).data:
    if i.display_name == NAME and i.lifecycle_state not in ('TERMINATED', 'TERMINATING'):
        log(result='exists', state=i.lifecycle_state, id=i.id); sys.exit(0)

ad = idn.list_availability_domains(T).data[0].name
for res, need in (('standard-a1-core-count', OCPUS), ('standard-a1-memory-count', MEM)):
    av = lim.get_resource_availability('compute', res, T, availability_domain=ad).data.available
    if av < need:
        log(result='error', reason=f'{res} available={av} < {need}: refusing (would exceed Always Free)'); sys.exit(1)

subnet = next(s for s in net.list_subnets(T).data if s.display_name == 'subnet-omonlyme')
img = next(i for i in comp.list_images(T, operating_system='Canonical Ubuntu', operating_system_version='24.04',
                                        shape='VM.Standard.A1.Flex', sort_by='TIMECREATED').data if 'Minimal' not in i.display_name)
pub = open('/srv/ytf/data/a1_ssh.pub').read().strip()
details = oci.core.models.LaunchInstanceDetails(
    availability_domain=ad, compartment_id=T, display_name=NAME, shape='VM.Standard.A1.Flex',
    shape_config=oci.core.models.LaunchInstanceShapeConfigDetails(ocpus=OCPUS, memory_in_gbs=MEM),
    source_details=oci.core.models.InstanceSourceViaImageDetails(image_id=img.id, boot_volume_size_in_gbs=BOOT_GB),
    create_vnic_details=oci.core.models.CreateVnicDetails(subnet_id=subnet.id, assign_public_ip=True, display_name=NAME),
    metadata={'ssh_authorized_keys': pub}, freeform_tags={'ytf': 'render-worker'})
try:
    r = comp.launch_instance(details).data
    log(result='created', id=r.id, image=img.display_name); sys.exit(0)
except oci.exceptions.ServiceError as e:
    cap = 'capacity' in (e.message or '').lower()
    log(result='out_of_capacity' if cap else 'error', status=e.status, code=e.code, msg=(e.message or '')[:200])
    sys.exit(3 if cap else 1)
