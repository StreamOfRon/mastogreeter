import os
from datetime import datetime

from dateutil.tz import tzutc
from mako.template import Template
import mastodon

MAX_DAYS = int(os.getenv('MAX_ACCOUNT_AGE', 30))  # Maximum age of accounts in days which will be considered
RESULT_LIMIT = int(os.getenv('API_RESULT_LIMIT', 200))  # The mastodon API seems to ignore values higher than this


class Greeter:
    def __init__(self):
        self._svc = mastodon.Mastodon(
            client_id=os.getenv('MASTODON_CLIENT_KEY'),
            client_secret=os.getenv('MASTODON_CLIENT_SECRET'),
            access_token=os.getenv('MASTODON_CLIENT_TOKEN'),
            api_base_url=os.getenv('MASTODON_BASE_URL'),
            user_agent='mastogreeter'
        )
        self._utcnow = datetime.utcnow().replace(tzinfo=tzutc())
        self._tpl = Template(filename="message.txt")
        self._instance_data = None
        self._contacted_list_id_value = None
        self._contacted = None
        self._active_user_ids = None

    @property
    def contacted(self):
        if self._contacted is None:
            first_page = self._svc.conversations(limit=RESULT_LIMIT)
            self._contacted = set(
                [
                    acct['id'] for c in first_page
                    for acct in c['accounts']
                    if self.not_too_old(c['last_status']['created_at'])
                ]
            )
            next_page = self._svc.fetch_next(first_page) if self.not_too_old(first_page[-1]['last_status']['created_at']) else None
            while next_page is not None:
                self._contacted.add(
                    [
                        acct['id'] for c in next_page
                        for acct in c['accounts']
                        if self.not_too_old(c['last_status']['created_at'])
                    ]
                )
                if self.too_old(next_page[-1]['last_status']['created_at']):
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
                limit=RESULT_LIMIT
            )
            self._active_user_ids = set(
                [
                    x['id'] for x in first_page
                    if self.not_too_old(x['created_at'])
                ]
            )
            next_page = self._svc.fetch_next(first_page) if self.not_too_old(first_page[-1]['created_at']) else None

            while next_page is not None:
                self._active_user_ids.add(
                    [
                        x['id'] for x in first_page
                        if self.not_too_old(x['created_at'])
                    ]
                )
                if self.too_old(next_page[-1]['created_at']):
                    break
                else:
                    next_page = self._svc.fetch_next(next_page)

        return self._active_user_ids

    def get_users_to_greet(self):
        return self.active_user_ids.difference(self.contacted)

    def greet_users(self, user_ids):
        for id in user_ids:
            if id not in self.contacted:
                account = self._svc.admin_account(id)
                message = self._tpl.render(
                    username=account['username'],
                    domain=self.instance_data['uri'],
                    site_title=self.instance_data['title'],
                    donation_link=os.getenv('DONATION_LINK')
                )
                self._contacted.add(id)
                self._svc.status_post(
                    status=message,
                    visibility="direct"
                )

    def too_old(self, timestamp):
        return (self._utcnow - timestamp).days > MAX_DAYS

    def not_too_old(self, timestamp):
        return not self.too_old(timestamp)


def main():
    greeter = Greeter()
    users_to_greet = greeter.get_users_to_greet()
    greeter.greet_users(users_to_greet)


if __name__ == '__main__':
    main()
