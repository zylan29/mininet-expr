"""VxLAN experiment

Two mininet vms are needed, the topology is:

   (vni_1)h1 --- (vtep)s1 ---- L3 underlay --- s1(vtep) --- h1(vni_2)
   (vni_2)h2 ---------|                         | --------- h2(vni_1)

vm1> sudo python vxlan.py 192.168.253.132 100 200
vm2> sudo python vxlan.py 192.168.253.131 200 100

vm1> h1 arping -c 2 10.0.0.2
vm1> h1 ping -c 1 10.0.0.2
vm1> h2 ip link set dev h2-eth0 down
vm1> h1 arping -c 2 10.0.0.2
vm1> h1 ping -c 1 10.0.0.2

"""

from mininet.cli import CLI
from mininet.net import Mininet
from mininet.topo import SingleSwitchTopo
import sys


if __name__ == '__main__':
    assert len(sys.argv) == 4, 'Usage: remote_ip vni_1 vni_2'

    remote_ip = sys.argv[1]
    vni_1 = int(sys.argv[2])
    vni_2 = int(sys.argv[3])

    net = Mininet(topo=SingleSwitchTopo(2))
    try:
        net.start()

        h1_obj = net.get('h1')
        h1_obj.cmd('ifconfig h1-eth0 10.0.0.1')

        h2_obj = net.get('h2')
        h2_obj.cmd('ifconfig h2-eth0 10.0.0.2')

        s1_obj = net.get('s1')
        s1_obj.cmd('ovs-vsctl add-port s1 vtep1')
        s1_obj.cmd('ovs-vsctl set interface vtep1 type=vxlan option:remote_ip=%s option:key=flow '
                   'ofport_request=9' % remote_ip)
        s1_obj.cmd('ovs-ofctl add-flow s1 in_port=1,actions=set_field:%d->tun_id,output:9' % vni_1)
        s1_obj.cmd('ovs-ofctl add-flow s1 in_port=9,tun_id=%d,actions=output:1' % vni_1)
        s1_obj.cmd('ovs-ofctl add-flow s1 in_port=2,actions=set_field:%d->tun_id,output:9' % vni_2)
        s1_obj.cmd('ovs-ofctl add-flow s1 in_port=9,tun_id=%d,actions=output:2' % vni_2)

        CLI(net)
    finally:
        net.stop()
