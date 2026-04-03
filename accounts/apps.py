from django.apps import AppConfig

def ready(self):
    import accounts.signals
    
class AccountsConfig(AppConfig):
    name = 'accounts'

