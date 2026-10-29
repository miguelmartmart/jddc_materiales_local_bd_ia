import unittest
from centro.windows_health import assess
from centro import core


class CapacityTests(unittest.TestCase):
    def sample(self,ram=4*1024**2,disk=30*1024**3):
        return {'system':[{'TotalVisibleMemorySize':8*1024**2,'FreePhysicalMemory':ram}],
                'disks':[{'DeviceID':'C:','Size':100*1024**3,'FreeSpace':disk}]}

    def test_available_capacity_is_not_general_health(self):
        rows=assess(self.sample())
        self.assertEqual([r['state'] for r in rows],['detectado','detectado'])
        self.assertTrue(all(r['source']=='windows' for r in rows))
        self.assertNotIn('correcto',[r['state'] for r in rows])
        self.assertIn('Instantanea',rows[0]['detail'])

    def test_low_absolute_and_relative_capacity(self):
        data=self.sample(ram=512*1024,disk=5*1024**3)
        self.assertEqual([r['state'] for r in assess(data)],['parcial','parcial'])
        data=self.sample(ram=2*1024**2,disk=20*1024**3)
        data['system'][0]['TotalVisibleMemorySize']=64*1024**2
        data['disks'][0]['Size']=1024*1024**3
        self.assertEqual([r['state'] for r in assess(data)],['parcial','parcial'])

    def test_boundaries_do_not_mean_critical(self):
        data=self.sample(ram=1024**2,disk=10*1024**3)
        self.assertEqual([r['state'] for r in assess(data)],['detectado','detectado'])

    def test_missing_data_stays_unknown(self):
        for data in (None,{},[],{'system':[],'disks':[]}):
            with self.subTest(data=data):self.assertTrue(all(r['state']=='no_comprobado' for r in assess(data)))

    def test_invalid_observations_are_not_echoed_or_green(self):
        for value in (True,-1,'PRIVATE',float('nan'),float('inf'),10**1000,1e308):
            data=self.sample();data['system'][0]['TotalVisibleMemorySize']=value
            with self.subTest(value=str(value)[:20]):
                result=assess(data)[0];self.assertEqual(result['state'],'no_comprobado');self.assertNotIn('PRIVATE',result['detail'])
        for value in (True,-1,'PRIVATE',float('nan'),float('inf'),10**1000):
            data=self.sample();data['disks'][0]['FreeSpace']=value
            self.assertEqual(assess(data)[1]['state'],'no_comprobado')

    def test_inconsistent_and_partial_disks(self):
        data=self.sample();data['system'][0]['FreePhysicalMemory']=99*1024**2
        data['disks'] += [None,{'DeviceID':'D:','Size':1,'FreeSpace':2}]
        rows=assess(data)
        self.assertEqual([r['state'] for r in rows],['no_comprobado','detectado','no_comprobado','no_comprobado'])

    def test_public_report_still_omits_capacity_details(self):
        report=core.public_report(assess(self.sample()))
        self.assertNotIn('GiB',str(report));self.assertNotIn('C:',str(report))
