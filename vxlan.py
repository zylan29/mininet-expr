"""

Topology:

vtep1(10.0.0.1)<---->h1-eth0(192.168.1.2)<---->s1-eth2
                                               s1-eth1<---->r0-eth0(192.168.1.1)
                                               s2-eth1<---->r0-eth1(172.168.1.1)
vtep2(10.0.0.2)<---->h2-eth0(172.168.1.2)<---->s2-eth2

Usage:
    h1 ping 10.0.0.2 -I vtep1
"""


from mininet.cli import CLI
from mininet.net import Mininet
from mininet.node import Node
from mininet.topo import Topo


class LinuxRouter(Node):
    "A Node with IP forwarding enabled."
    def config(self, **params):
        super(LinuxRouter, self).config(**params)
        # Enable forwarding on the router
        self.cmd('sysctl net.ipv4.ip_forward=1')

    def terminate(self):
        self.cmd('sysctl net.ipv4.ip_forward=0' )
        super(LinuxRouter, self).terminate()


class VxLANTopo(Topo):

    def __init__(self):
        Topo.__init__(self)
        r0_ip1 = '192.168.1.1'  # IP address for r1-eth1
        r0_mask1 = '24'
        r0_ip2 = '172.168.1.1'
        r0_mask2 = '24'
        r0 = self.addNode('r0', cls=LinuxRouter, ip='%s/%s' % (r0_ip1, r0_mask1))

        s1, s2 = [self.addSwitch(s) for s in ('s1', 's2')]

        self.addLink(s1, r0, intfName2='r0-eth0', params2={'ip': '%s/%s' % (r0_ip1, r0_mask1)})
        self.addLink(s2, r0, intfName2='r0-eth1', params2={'ip': '%s/%s' % (r0_ip2, r0_mask2)})

        h1_ip = '192.168.1.2'
        h1_mask = '24'
        h2_ip = '172.168.1.2'
        h2_mask = '24'
        h1 = self.addHost('h1', ip='%s/%s'%(h1_ip, h1_mask), defaultRoute='via %s' % r0_ip1)
        h2 = self.addHost('h2', ip='%s/%s'%(h2_ip, h2_mask), defaultRoute='via %s' % r0_ip2)
        self.addLink(h1, s1)
        self.addLink(h2, s2)


if __name__ == '__main__':
    net = Mininet(topo=VxLANTopo(), controller=None)
    try:
        net.start()

        # we setup VxLAN tunnel without a controller.
        v1_ip = '10.0.0.1'
        v1_mac = '54:8:10:0:0:1'
        vni_1 = 99
        h1_obj = net.get('h1')
        h1_obj.cmd('ip link add vtep1 type vxlan id %d dev h1-eth0 l2miss l3miss rsc proxy nolearning' % vni_1)
        h1_obj.cmd('ip link set vtep1 address 54:8:10:0:0:1')
        h1_obj.cmd('ip address add 10.0.0.1/8 dev vtep1')
        h1_obj.cmd('ip link set up vtep1')

        v2_ip = '10.0.0.2'
        v2_mac = '54:8:10:0:0:2'
        vni_2 = vni_1 + 1
        h2_obj = net.get('h2')
        h2_obj.cmd('ip link add vtep2 type vxlan id %d dev h2-eth0 l2miss l3miss rsc proxy nolearning' % vni_2)
        h2_obj.cmd('ip link set vtep2 address %s' % v2_mac)
        h2_obj.cmd('ip address add %s/8 dev vtep2' % v2_ip)
        h2_obj.cmd('ip link set up vtep2')

        # Since h1(192.*) and h2(172.*) are NOT in the same broadcast zone, we should manually setup ARP and FDB table.
        h1_obj.cmd('ip neighbor add %s lladdr %s dev vtep1 nud permanent' % (v2_ip, v2_mac))
        h1_obj.cmd('bridge fdb add %s dev vtep1 self dst 172.168.1.2 vni %d' % (v2_mac, vni_2))

        h2_obj.cmd('ip neighbor add %s lladdr %s dev vtep2 nud permanent' % (v1_ip, v1_mac))
        h2_obj.cmd('bridge fdb add %s dev vtep2 self dst 192.168.1.2 vni %d' % (v1_mac, vni_1))

        s1_obj = net.get('s1')
        s1_obj.cmd('ovs-ofctl add-flow s1 "in_port=1, actions=output:2"')
        s1_obj.cmd('ovs-ofctl add-flow s1 "in_port=2, actions=output:1"')
        s2_obj = net.get('s2')
        s2_obj.cmd('ovs-ofctl add-flow s2 "in_port=1, actions=output:2"')
        s2_obj.cmd('ovs-ofctl add-flow s2 "in_port=2, actions=output:1"')

        net.pingAll()

        CLI(net)

        h1_obj.cmd('ip link delete vtep1')
        h2_obj.cmd('ip link delete vtep2')
    finally:
        net.stop()
