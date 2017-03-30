"""VxLAN experiment

Two mininet vms are needed, the topology is:

   (vni_1)h1 --- (vtep)s1 ---- L3 underlay --- s1(vtep) --- h1(vni_2)
   (vni_2)h2 ---------|                         | --------- h2(vni_1)

vm1> sudo python vxlan.py 192.168.253.132 10.0.0.1 10.0.0.2
vm2> sudo python vxlan.py 192.168.253.131 10.0.0.3 10.0.0.4

10.0.0.1 and 10.0.0.3 are in the same vlan and vxlan.
10.0.0.2 and 10.0.0.4 are in the same vlan and vxlan.

vm1> h1 arping -c 2 10.0.0.2
vm1> h1 ping -c 1 10.0.0.2
vm1> h1 arping -c 2 10.0.0.3
vm1> h1 ping -c 1 10.0.0.3
"""

from mininet.cli import CLI
from mininet.node import Host
from mininet.net import Mininet
from mininet.topo import SingleSwitchTopo
from mininet.topo import Topo
import sys


class VLANHost( Host ):
    "Host connected to VLAN interface"

    vlanIntf = ''

    def config( self, vlan=100, **params ):
        """Configure VLANHost according to (optional) parameters:
           vlan: VLAN ID for default interface"""

        r = super( VLANHost, self ).config( **params )

        intf = self.defaultIntf()
        # remove IP from default, "physical" interface
        self.cmd( 'ifconfig %s inet 0' % intf )
        # create VLAN interface
        self.cmd( 'vconfig add %s %d' % ( intf, vlan ) )
        # assign the host's IP to the VLAN interface
        self.cmd( 'ifconfig %s.%d inet %s' % ( intf, vlan, params['ip'] ) )
        # update the intf name and host's intf map
        newName = '%s.%d' % ( intf, vlan )
        # update the (Mininet) interface to refer to VLAN interface name
        intf.name = newName
        # add VLAN interface to host's name to intf map
        self.nameToIntf[ newName ] = intf
        self.vlanIntf = newName

        return r

hosts = { 'vlan': VLANHost }


class VLANStarTopo( Topo ):
    """Example topology that uses host in multiple VLANs

       The topology has a single switch. There are k VLANs with
       n hosts in each, all connected to the single switch. There
       are also n hosts that are not in any VLAN, also connected to
       the switch."""

    def build( self, k=2, vlanBase=100):
        s1 = self.addSwitch( 's1' )
        for i in range(k):
            vlan = vlanBase + i
            name = 'h%d' % (i+1)
            h = self.addHost(name, cls=VLANHost, vlan=vlan)
            self.addLink(h, s1)


if __name__ == '__main__':
    assert len(sys.argv) == 4, 'Usage: remote_ip ip_1 ip_2'

    remote_ip = sys.argv[1]
    ip_1 = sys.argv[2]
    ip_2 = sys.argv[3]

    vni_1 = 100
    vni_2 = 200

    net = Mininet(topo=VLANStarTopo())
    try:
        net.start()

        h1_obj = net.get('h1')
        h1_obj.cmd('ifconfig %s %s' % (h1_obj.vlanIntf, ip_1))

        h2_obj = net.get('h2')
        h2_obj.cmd('ifconfig %s %s' % (h2_obj.vlanIntf, ip_2))

        # Setup per-port VNI
        s1_obj = net.get('s1')
        s1_obj.cmd('ovs-vsctl add-port s1 vtep1')
        s1_obj.cmd('ovs-vsctl set interface vtep1 type=vxlan option:remote_ip=%s option:key=%d '
                   'ofport_request=9' % (remote_ip, vni_1))
        s1_obj.cmd('ovs-ofctl add-flow s1 in_port=1,actions=set_tunnel:%d,output:9' % vni_1)
        s1_obj.cmd('ovs-ofctl add-flow s1 in_port=9,tun_id=%d,actions=output:1' % vni_1)

        s1_obj.cmd('ovs-vsctl add-port s1 vtep2')
        s1_obj.cmd('ovs-vsctl set interface vtep2 type=vxlan option:remote_ip=%s option:key=%d '
                   'ofport_request=10' % (remote_ip, vni_2))
        s1_obj.cmd('ovs-ofctl add-flow s1 in_port=2,actions=set_tunnel:%d,output:10' % vni_2)
        s1_obj.cmd('ovs-ofctl add-flow s1 in_port=10,tun_id=%d,actions=output:2' % vni_2)

        CLI(net)
    finally:
        net.stop()
