import logging
import os
import sys
from datetime import datetime
from datetime import timezone

import mastodon
from mako.template import Template
from pythonjsonlogger import jsonlogger


log = logging.getLogger()
log.setLevel(os.getenv("LOG_LEVEL", "INFO").upper())
log_handler = logging.StreamHandler(sys.stdout)
log_handler.setFormatter(jsonlogger.JsonFormatter())
log.addHandler(log_handler)


class Greeter:
    def __init__(self):
        self._svc = mastodon.Mastodon(
            client_id=os.getenv('MASTODON_CLIENT_KEY'),
            client_secret=os.getenv('MASTODON_CLIENT_SECRET'),
            access_token=os.getenv('MASTODON_CLIENT_TOKEN'),
            api_base_url=os.getenv('MASTODON_BASE_URL'),
            user_agent='mastogreeter'
        )
        self._max_days = int(os.getenv('MAX_ACCOUNT_AGE', 30))  # Maximum age of accounts in days which will be considered
        self._max_to_greet = int(os.getenv('MAX_GREETINGS_PER_RUN', 0))  # Limit how many greetings you'll send in a single run
        self._result_limit = int(os.getenv('API_RESULT_LIMIT', 200))  # The mastodon API seems to ignore values higher than this
        self._skip_ids = [
            intval for uid in os.getenv('SKIP_IDS', "").split(',')
            if (intval := self._intval_or_none(uid)) is not None
        ]
        self._utcnow = datetime.now(tz=timezone.utc)
        self._tpl = Template(filename="message.txt")
        self._instance_data = None
        self._contacted_list_id_value = None
        self._contacted = None
        self._active_user_ids = None
        self._log = self._get_logger()

    @property
    def contacted(self):
        if self._contacted is None:
            first_page = self._svc.conversations(limit=self._result_limit)
            self._contacted = set(
                [
                    acct['id'] for c in first_page
                    for acct in c['accounts']
                    if self.not_too_old(self._get_last_status_age(c))
                ]
            )
            if len(first_page) > 0:
                next_page = self._svc.fetch_next(first_page) if self.not_too_old(self._get_last_status_age(first_page[-1])) else None
                while next_page is not None:
                    self._contacted.update(
                        [
                            acct['id'] for c in next_page
                            for acct in c['accounts']
                            if self.not_too_old(self._get_last_status_age(c))
                        ]
                    )
                    if len(next_page) < 1 or self.too_old(self._get_last_status_age(next_page[-1])):
                        break
                    else:
                        next_page = self._svc.fetch_next(next_page)
        return self._contacted

    @property
    def instance_data(self):
        if self._instance_data is None:
            self._instance_data = self._svc.instance()

        return self._instance_data

    @property
    def active_user_ids(self):
        if self._active_user_ids is None:
            first_page = self._svc.admin_accounts_v2(
                origin="local",
                status="active",
                limit=self._result_limit
            )
            self._log.debug(f"Found {len(first_page)} active users in this page")
            self._active_user_ids = set(
                [
                    x['id'] for x in first_page
                    if self.not_too_old(x['created_at'])
                    and x['confirmed']
                ]
            )
            self._log.debug(f"Now have {len(self._active_user_ids)} known active users")
            if len(first_page) > 0:
                next_page = self._svc.fetch_next(first_page) if self.not_too_old(first_page[-1]['created_at']) else None
                while next_page is not None:
                    self._active_user_ids.update(
                        [
                            x['id'] for x in next_page
                            if self.not_too_old(x['created_at'])
                        ]
                    )
                    self._log.debug(f"Now have {len(self._active_user_ids)} known active users")
                    if len(next_page) < 1 or self.too_old(next_page[-1]['created_at']):
                        break
                    else:
                        next_page = self._svc.fetch_next(next_page)

        return self._active_user_ids

    def get_users_to_greet(self):
        return [id for id in self.active_user_ids.difference(self.contacted) if id not in self._skip_ids]

    def greet_users(self, user_ids):
        user_ids = sorted(user_ids)  # Always sort in ascending order so those who've waited the longest get greeted first
        greeted = 0
        for id in user_ids:
            if id not in self.contacted:
                if self._max_to_greet > 0 and greeted >= self._max_to_greet:
                    break
                else:
                    greeted += 1

                account = self._svc.admin_account(id)
                message = self._tpl.render(
                    username=account['username'],
                    domain=self.instance_data['uri'],
                    site_title=self.instance_data['title'],
                    donation_link=os.getenv('DONATION_LINK')
                )
                self._contacted.add(id)
                self._log.info(f"Sending greeting to @{account['username']}@{self.instance_data['uri']}")
                self._svc.status_post(
                    status=message,
                    visibility="direct"
                )
        self._log.info(f"Sent greetings to {greeted} user(s)")

    def too_old(self, timestamp):
        return (self._utcnow - timestamp).days > self._max_days

    def not_too_old(self, timestamp):
        return not self.too_old(timestamp)

    def _get_logger(self):
        if 'log' not in globals():
            log = logging.getLogger()
            log.setLevel(os.getenv("LOG_LEVEL", "INFO").upper())
            log_handler = logging.StreamHandler(sys.stdout)
            log_handler.setFormatter(jsonlogger.JsonFormatter())
            log.addHandler(log_handler)
            return log
        else:
            return globals()['log']

    def _get_last_status_age(self, conversation):
        if not [acct for acct in conversation.get('accounts') if acct.get('suspended', False)]:
            try:
                return conversation.get('last_status').get('created_at')
            except AttributeError:
                log.exception("Could not parse conversation {}".format(conversation))
        return self._utcnow

    def _intval_or_none(self, string):
        try:
            return int(string)
        except ValueError:
            return None

def main():
    greeter = Greeter()
    users_to_greet = greeter.get_users_to_greet()
    log.info(f"Found {len(users_to_greet)} active user(s) to greet")
    greeter.greet_users(users_to_greet)


if __name__ == '__main__':
    main()
