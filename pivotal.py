import requests
import json
import os

from pprint import pprint

debug = False

if debug:
    import logging

    # These two lines enable debugging at httplib level (requests->urllib3->http.client)
    # You will see the REQUEST, including HEADERS and DATA, and RESPONSE with HEADERS but without DATA.
    # The only thing missing will be the response.body which is not logged.
    try:
        import http.client as http_client
    except ImportError:  # PY2
        import httplib as http_client
    http_client.HTTPConnection.debuglevel = 1

    # You must initialize logging, otherwise you'll not see debug output.
    logging.basicConfig()
    logging.getLogger().setLevel(logging.DEBUG)
    requests_log = logging.getLogger("requests.packages.urllib3")
    requests_log.setLevel(logging.DEBUG)
    requests_log.propagate = True


class GitHub(object):

    def __init__(self, owner=None, repo=None):
        self.base_url = 'https://api.github.com/repos/%s/%s/' % (owner, repo)
        self.headers = {
            'Content-Type': 'application/json',
            'User-Agent': owner
        }

    def get_pull(self, pull_number):
        """
        Get information about a pull request.

        Parameters
        ----------
        id : int
            The pull request number.

        Returns
        -------
        dict
            A dictionary with information about the pull request.
        """
        url = self.base_url + 'pulls/%s' % pull_number

        req = requests.get(headers=self.headers, url=url)

        return req.json()

    def get_pulls(self):
        """
        Get information about pull requests.

        Returns
        -------
        list
            List of dictionaries with information about pull requests.
        """
        url = self.base_url + 'pulls'

        req = requests.get(headers=self.headers, url=url)

        return req.json()


class Pivotal(object):

    def __init__(self, project=None, token=None):
        self.base_url = 'https://www.pivotaltracker.com/services/v5/projects/%s/' % project
        self.headers = {
            'X-TrackerToken': token,
            'Content-Type': 'application/json'
        }
        self.people = None

    def get_story(self, id):
        """
        Get story by ID.

        Parameters
        ----------
        id : int
            A person ID.

        Returns
        -------
        dict
            A metadata dictionary with data about matching story.
        """
        url = self.base_url + 'stories/{story}'

        req = requests.get(headers=self.headers, url=url.format(story=id))

        return req.json()

    def get_stories(self, query):
        """
        Get stories by search query.

        Parameters
        ----------
        query : str
            A search query.
            See: https://www.pivotaltracker.com/help/articles/advanced_search/

        Returns
        -------
        list
            A list of metadata dictionaries with data about matching stories.
        """
        url = self.base_url + 'search?query={query}'

        req = requests.get(headers=self.headers, url=url.format(query=query))

        return req.json()['stories']['stories']

    def get_activity(self, story):
        """
        Get story activity.

        Parameters
        ----------
        story : int
            A story ID.

        Returns
        -------
        list
            A list of metadata dictionaries with data about activity on the story.
        """
        story = story['id'] if isinstance(story, dict) else story

        url = self.base_url + 'stories/{story}/activity'

        req = requests.get(headers=self.headers, url=url.format(story=story))

        return req.json()

    def get_people(self):
        """
        Get people associated with the project.

        Returns
        -------
        list
            A list of metadata dictionaries with data about people on the project.
        """
        url = self.base_url + 'memberships'

        req = requests.get(headers=self.headers, url=url)

        return req.json()

    def get_person(self, id):
        """
        Get information about the person with the given ID.

        Parameters
        ----------
        id : int
            A person ID.

        Returns
        -------
        dict
            A dictionary of information about the person.
        """
        if self.people is None:
            self.people = self.get_people()

        for person in self.people:
            if person['person']['id'] == id:
                return person['person']

        return None

    def get_pull(self, story):
        """
        Get the pull request associated with a story (if any).

        Parameters
        ----------
        story : str
            A story ID.

        Returns
        -------
        str or None
            The pull request ID.
        """
        story = story['id'] if isinstance(story, dict) else story

        activity = self.get_activity(story)

        for act in activity:
            if act['kind'] == 'pull_request_create_activity':
                for change in act['changes']:
                    if change['kind'] == 'pull_request':
                        return change['new_values']['number']

        return None

    def get_story_info(self, query):
        """
        Get information about all stories that match the given query.

        Parameters
        ----------
        query : str
            A search query.
            See: https://www.pivotaltracker.com/help/articles/advanced_search/

        Returns
        -------
        list
            List of metadata dictionaries for each matching story.
        """
        stories = self.get_stories(query)

        info = []

        for story in stories:
            story_info = {
                'id': story['id'],
                'name': story['name'],
                'kind': story['kind'].capitalize(),
                'state': story['current_state'],
                'owner': self.get_person(story['owned_by_id'])['name'],
                'pull': self.get_pull(story)
            }
            info.append(story_info)

        return info

    def set_state(self, story, state):
        """
        Change story state.

        Parameters
        ----------
        story : int
            A story ID.
        state : str
            The new story state.

        Returns
        -------
        dict
            The response from the server.
        """
        story = story['id'] if isinstance(story, dict) else story

        url = self.base_url + 'stories/{story}'

        req = requests.put(headers=self.headers, url=url.format(story=story),
                           data=json.dumps({'current_state': state}))

        rsp = req.json()
        if 'error' in rsp:
            raise RuntimeError('State change not successful:\n %s' % str(rsp))
        return req.json()

    def deliver(self, pull=None):
        """
        Deliver any started or finished stories that have the specied pull request attached.

        Parameters
        ---------
        pull : int
            The pull request number

        Returns
        -------
        dict
            The response from the server.
        """
        stories =  self.get_story_info('state:started or state:finished')

        for story in stories:
            print('------------')

            print('{kind} #{id} ({state}), {owner}'.format(**story))
            print(story['name'])

            if story['pull']:
                print('PR #%d' % story['pull'])
                if story['pull'] == pull:
                    print('Transitioning Story #%d' % story['id'], '(%s)' % story['owner'], story['name'], 'to "delivered".')
                    response = self.set_state(story['id'], 'delivered')
                    pprint(response)

            print('------------')


def transition_merged_stories():
    """
    Get finished stories on Pivotal and check GitHub to see if the associated PR has been merged.
    Transition stories that have been merged to 'delivered' in Pivotal.
    """
    token = os.getenv('PIVOTAL_TOKEN')
    if not token:
        msg = 'Please provide your Pivotal API token via an environment variable: PIVOTAL_TOKEN\n' \
              'Your API Token can be found on your Profile page: https://www.pivotaltracker.com/profile'
        raise RuntimeError(msg)

    pivotal = Pivotal(project='1885757', token=token)
    github = GitHub(owner='OpenMDAO', repo='OpenMDAO')

    finished =  pivotal.get_finished()

    for story in finished:
        print('------------')

        print('{kind} #{id} ({state}), {owner}'.format(**story))
        print(story['name'])

        if story['pull']:
            print('PR #%d' % story['pull'])

            pull = github.get_pull(story['pull'])
            print(pull['title'])
            print(pull['body'])
            print('merged:', pull['merged'])

            if pull['merged']:
                print('Transitioning Story #%d' % story['id'], '(%s)' % story['owner'], story['name'], 'to "delivered".')
                response = pivotal.set_state(story['id'], 'delivered')
                pprint(response)

        print('------------')


if __name__ == '__main__':
    transition_merged_stories()

