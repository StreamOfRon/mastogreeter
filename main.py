from datetime import datetime
import os
from dateutil.tz import tzutc

from mako.template import Template
from mastodon import Mastodon


MAX_DAYS = 30  # Maximum age of accounts in days which will be considered
RESULT_LIMIT = 200  # The mastodon API seems to ignore values higher than this


class Greeter:
    def __init__(self):
        self._svc = Mastodon(
            client_id=os.getenv('MASTODON_CLIENT_KEY'),
            client_secret=os.getenv('MASTODON_CLIENT_SECRET'),
            access_token=os.getenv('MASTODON_CLIENT_TOKEN'),
            api_base_url=os.getenv('MASTODON_BASE_URL'),
            user_agent='mastogreeter'
        )
        self._instance_data = None
        self._contacted_list_id_value = None
        self._contacted = None
        self._all_active_user_id_values = None

    @property
    def contacted(self):
        if self._contacted is None:
            resp = self._svc.list_accounts(self._contacted_list_id, limit=RESULT_LIMIT)
            self._contacted = set([x.get('id') for x in self._svc.fetch_remaining(resp)])
        return self._contacted

    @property
    def instance_data(self):
        if self._instance_data is None:
            self._instance_data = self._svc.instance()

        return self._instance_data

    @property
    def _all_active_user_ids(self):
        utc_now = datetime.utcnow().replace(tzinfo=tzutc())
        if self._all_active_user_id_values is None:
            first_page = self._svc.admin_accounts_v2(
                origin="local",
                status="active",
                limit=RESULT_LIMIT
            )
            self._all_active_user_id_values = set([x['id'] for x in first_page if (utc_now - x['created_at']) <= MAX_DAYS])
            next_page = self._svc.fetch_next(first_page) if (utc_now - first_page[-1]['created_at']).days <= MAX_DAYS else None

            while next_page is not None:
                self._all_active_user_id_values.add([x['id'] for x in first_page if (utc_now - x['created_at']) <= MAX_DAYS])
                if (utc_now - next_page[-1]['created_at']).days > MAX_DAYS:
                    break

        return self._all_active_user_id_values

    @property
    def _contacted_list_id(self):
        if self._contacted_list_id_value is None:
            list_ids = [x.get('id') for x in self._svc.lists() if x.get('title') == 'contacted']
            if len(list_ids) == 0:
                result = self._svc.list_create('contacted')
                self._contacted_list_id_value = result['id']
            else:
                self._contacted_list_id_value = list_ids[0]

        return self._contacted_list_id_value

    def greet_new_users(self):
        userids_to_contact = self._all_active_user_ids.difference(self._contacted_list_id)
        
    def _render_message(self, **kwargs):
        tpl = Template(filename='message.txt')
        return tpl.render(**kwargs)
