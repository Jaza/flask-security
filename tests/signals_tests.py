from __future__ import with_statement

from mock import (patch, call)

from flask_security.utils import (capture_registrations, capture_reset_password_requests, capture_signals)
from flask_security.signals import (user_registered, user_confirmed,
                                    confirm_instructions_sent, login_instructions_sent,
                                    password_reset, reset_password_instructions_sent)
from tests import SecurityTest


def compare_user(a, b):
    """ Helper to compare two users."""
    return a.id == b.id and a.email == b.email and a.password == b.password


class RegisterableSignalsTests(SecurityTest):

    AUTH_CONFIG = {
        'SECURITY_CONFIRMABLE': True,
        'SECURITY_REGISTERABLE': True,
    }

    def test_register(self):
        e = 'dude@lp.com'
        with capture_signals() as mocks:
            self.register(e)
        user = self.app.security.datastore.find_user(email='dude@lp.com')
        self.assertEqual(mocks.signals_sent(), set([user_registered]))
        calls = mocks[user_registered]
        self.assertEqual(len(calls), 1)
        args, kwargs = calls[0]
        self.assertTrue(compare_user(args[0]['user'], user))
        self.assertIn('confirm_token', args[0])
        self.assertEqual(kwargs['app'], self.app)


class ConfirmableSignalsTests(SecurityTest):

    AUTH_CONFIG = {
        'SECURITY_CONFIRMABLE': True,
        'SECURITY_REGISTERABLE': True,
    }

    def test_confirm(self):
        e = 'dude@lp.com'
        with capture_registrations() as registrations:
            self.register(e)
            token = registrations[0]['confirm_token']
        with capture_signals() as mocks:
            self.client.get('/confirm/' + token, follow_redirects=True)
        user = self.app.security.datastore.find_user(email='dude@lp.com')
        self.assertTrue(mocks.signals_sent(), set([user_confirmed]))
        calls = mocks[user_confirmed]
        self.assertEqual(len(calls), 1)
        args, kwargs = calls[0]
        self.assertEqual(args[0].id, user.id)
        self.assertEqual(kwargs['app'], self.app)

    def test_confirm_bad_token(self):
        e = 'dude@lp.com'
        with capture_registrations() as registrations:
            self.register(e)
            token = registrations[0]['confirm_token']
        with capture_signals() as mocks:
            self.client.get('/confirm/bogus', follow_redirects=True)
        self.assertEqual(mocks.signals_sent(), set())

    def test_confirm_twice(self):
        e = 'dude@lp.com'
        with capture_registrations() as registrations:
            self.register(e)
            token = registrations[0]['confirm_token']
        self.client.get('/confirm/' + token, follow_redirects=True)
        self.logout()
        with capture_signals() as mocks:
            self.client.get('/confirm/' + token, follow_redirects=True)
        # TODO: this refires the signal (len==1 instead of 0), is that the desired behaviour?
        self.assertEqual(mocks.signals_sent(), set([user_confirmed]))

    def test_send_confirmation_bad_email(self):
        with capture_signals() as mocks:
            self._post('/confirm', data=dict(email='bogus@bogus.com'))
        self.assertEqual(mocks.signals_sent(), set())

    def test_resend_confirmation(self):
        e = 'dude@lp.com'
        self.register(e)
        with capture_signals() as mocks:
            self._post('/confirm', data={'email': e})
        user = self.app.security.datastore.find_user(email='dude@lp.com')
        self.assertEqual(mocks.signals_sent(), set([confirm_instructions_sent]))
        calls = mocks[confirm_instructions_sent]
        self.assertEqual(len(calls), 1)
        args, kwargs = calls[0]
        self.assertTrue(compare_user(args[0], user))
        self.assertEqual(kwargs['app'], self.app)


class RecoverableSignalsTests(SecurityTest):

    AUTH_CONFIG = {
        'SECURITY_RECOVERABLE': True,
        'SECURITY_RESET_PASSWORD_ERROR_VIEW': '/',
        'SECURITY_POST_FORGOT_VIEW': '/'
    }

    def test_reset_password(self):
        with capture_signals() as mocks:
            self.client.post('/reset',
                             data=dict(email='joe@lp.com'),
                             follow_redirects=True)
        self.assertEqual(mocks.signals_sent(), set([reset_password_instructions_sent]))
        user = self.app.security.datastore.find_user(email='joe@lp.com')
        calls = mocks[reset_password_instructions_sent]
        self.assertEqual(len(calls), 1)
        args, kwargs = calls[0]
        self.assertTrue(compare_user(args[0]['user'], user))
        self.assertIn('token', args[0])
        self.assertEqual(kwargs['app'], self.app)


class PasswordlessTests(SecurityTest):

    AUTH_CONFIG = {
        'SECURITY_PASSWORDLESS': True
    }

    def test_login_request_for_inactive_user(self):
        with capture_signals() as mocks:
            self.client.post('/login',
                             data=dict(email='tiya@lp.com'),
                             follow_redirects=True)
        self.assertEqual(mocks.signals_sent(), set())


    def test_request_login_token_sends_email_and_can_login(self):
        e = 'matt@lp.com'

        with capture_signals() as mocks:
            self.client.post('/login',
                             data=dict(email=e),
                             follow_redirects=True)
        self.assertEqual(mocks.signals_sent(), set([login_instructions_sent]))
        user = self.app.security.datastore.find_user(email='matt@lp.com')
        calls = mocks[login_instructions_sent]
        self.assertEqual(len(calls), 1)
        args, kwargs = calls[0]
        self.assertTrue(compare_user(args[0]['user'], user))
        self.assertIn('login_token', args[0])
        self.assertEqual(kwargs['app'], self.app)

