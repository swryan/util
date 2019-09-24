#!/usr/bin/env python
from __future__ import print_function
from pprint import pprint

import os
import sys

import tornado.ioloop
import tornado.web

import json

from pivotal import Pivotal

#
# set up interface to Pivotal
#
token = os.getenv('PIVOTAL_TOKEN')
if not token:
    msg = 'Please provide your Pivotal API token via an environment variable: PIVOTAL_TOKEN\n' \
          'Your API Token can be found on your Profile page: https://www.pivotaltracker.com/profile'
    raise RuntimeError(msg)

pivotal = Pivotal(project='1885757', token=token)


class GitHubHandler(tornado.web.RequestHandler):
    def get(self):
        """
        Receive and process a message from GitHub
        """
        self.write("Well, Hello there!")

    def post(self):
        """
        Receive and process a message from GitHub
        """
        print('--------------------------------------')
        print('POST received:', self.request.headers.get('X-GitHub-Event'))
        print('-------  HEADERS -------')
        pprint(dict(self.request.headers))
        print('-------  BODY -------')
        data = json.loads(self.request.body)
        pprint(list(data.keys()))
        # pprint(data)

        evt = self.request.headers.get('X-GitHub-Event')
        if evt == 'pull_request':
            print('ohhhh... a pull request!!')
            data = json.loads(self.request.body)
            print('action:', data['action'])
            print('merged:', data['pull_request']['merged'])
            if data['action'] == 'closed' and data['pull_request']['merged']:
                print('ask pivotal to deliver PR #', data['number'])
                pivotal.deliver(pull=data['number'])
            sys.stdout.flush()


if __name__ == "__main__":
    app = tornado.web.Application([
        (r"/", GitHubHandler),
    ], debug=True)

    app.listen(23997)
    tornado.ioloop.IOLoop.current().start()

