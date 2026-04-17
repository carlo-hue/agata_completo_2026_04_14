CLIENT_ID = "REPLACE_WITH_AZURE_CLIENT_ID"
CLIENT_SECRET = "REPLACE_WITH_AZURE_CLIENT_SECRET"
TENANT_ID = "REPLACE_WITH_AZURE_TENANT_ID"

AUTHORITY = f"https://login.microsoftonline.com/{TENANT_ID}"
REDIRECT_URI = "https://app-test.astrogen.it/get_token"
SCOPE = ["User.Read"]

#quiz
QUIZ_UPLOAD_FOLDER = "/percorso/assoluto/alla/cartella/static/diplomas"

#effemreidi
EPH_DATA_DIRECTORY = '/var/www/astrogen/effemeridi/static/skyfield_data'
