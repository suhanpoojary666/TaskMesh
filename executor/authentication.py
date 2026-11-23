import hashlib
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from .models import APIKey

class APIKeyAuthentication(BaseAuthentication):

    def authenticate(self, request):

        api_key=request.headers.get("X-API-Key") #from the http request retrive the api key header


        if not api_key:
            return None

        key_hash = hashlib.sha256(api_key.encode()).hexdigest()

        try:
            api_key_obj = APIKey.objects.get(key_hash=key_hash, is_active=True)

        except APIKey.DoesNotExist:
            raise AuthenticationFailed("Invalid API Key")

        return (api_key_obj.owner, api_key_obj)  #DRF handles from here