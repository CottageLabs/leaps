SECRET_KEY = "default-key" # make this something secret in your overriding app.cfg

# contact info
ADMIN_NAME = "Cottage Labs"
ADMIN_EMAIL = ""

# service info
SERVICE_NAME = "Portality"
SERVICE_TAGLINE = ""
HOST = "0.0.0.0"
DEBUG = True
PORT = 5004

# list of superuser account names
SUPER_USER = ["test"]

PUBLIC_REGISTER = True # Can people register publicly? If false, only the superuser can create new accounts
SHOW_LOGIN = True # if this is false the login link is not shown in the default template, but login is not necessarily disabled

# if you make remote calls e.g. to google fonts or js plugins but have to run offline, then wrap those parts of your templates with a check for this, and then you can set it to true if you need to run your system without online access
OFFLINE = False 

# elasticsearch settings
ELASTIC_SEARCH_HOST = "http://127.0.0.1:9200"
ELASTIC_SEARCH_DB = "portality"
INITIALISE_INDEX = True # whether or not to try creating the index and required index types on startup
NO_QUERY_VIA_API = ['account'] # list index types that should not be queryable via the API
PUBLIC_ACCESSIBLE_JSON = True # can not logged in people get JSON versions of pages by querying for them?


# if search filter is true, anonymous users only see visible and accessible pages in query results
# if search sort and order are set, all queries from /query will return with default search unless one is provided
# placeholder image can be used in search result displays
ANONYMOUS_SEARCH_FILTER = True
SEARCH_SORT = ''
SEARCH_SORT_ORDER = ''


# a dict of the ES mappings. identify by name, and include name as first object name
# and identifier for how non-analyzed fields for faceting are differentiated in the mappings
FACET_FIELD = ".exact"
MAPPINGS = {
    "student" : {
        "student" : {
            "dynamic_templates" : [
                {
                    "default" : {
                        "match" : "*",
                        "match_mapping_type": "string",
                        "mapping" : {
                            "type" : "multi_field",
                            "fields" : {
                                "{name}" : {"type" : "{dynamic_type}", "index" : "analyzed", "store" : "no"},
                                "exact" : {"type" : "{dynamic_type}", "index" : "not_analyzed", "store" : "yes"}
                            }
                        }
                    }
                }
            ]
        }
    }
}
MAPPINGS['account'] = {'account':MAPPINGS["student"]["student"]}
MAPPINGS['school'] = {'school':MAPPINGS["student"]["student"]}
MAPPINGS['subject'] = {'subject':MAPPINGS["student"]["student"]}
MAPPINGS['level'] = {'level':MAPPINGS["student"]["student"]}
MAPPINGS['grade'] = {'grade':MAPPINGS["student"]["student"]}
MAPPINGS['institution'] = {'institution':MAPPINGS["student"]["student"]}
MAPPINGS['advancedlevel'] = {'advancedlevel':MAPPINGS["student"]["student"]}
MAPPINGS['simd'] = {'simd':MAPPINGS["student"]["student"]}
MAPPINGS['archive'] = {'archive':MAPPINGS["student"]["student"]}

