from adhocracy.tests import TestController
from adhocracy.tests.testtools import tt_make_user


class TestText(TestController):

    def test_render(self):
        from adhocracy.lib.text import render
        source = ('header\n'
                  '========')
        result = render(source)
        self.assertEqual(result, u'<h1>header</h1>\n')

    def test_render_no_substitution(self):
        from adhocracy.lib.text import render
        tt_make_user('pudo')
        source = '@pudo'
        result = render(source, substitutions=False)
        self.assertEqual(result, u'<p>@pudo</p>\n')

    def test_render_user_substitution(self):
        from adhocracy.lib.text import render
        tt_make_user('pudo')
        source = '@pudo'
        result = render(source, substitutions=True)
        self.assertTrue(u'http://test.test.lan/user/pudo"' in result)
