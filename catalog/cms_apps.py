# catalog/cms_apps.py
from cms.app_base import CMSApp
from cms.apphook_pool import apphook_pool
from django.utils.translation import gettext_lazy as _


@apphook_pool.register
class CatalogApphook(CMSApp):
    app_name = "catalog"
    name = _("Catalog Application")

    def get_urls(self, page=None, language=None, **kwargs):
        return ["catalog.urls"]
