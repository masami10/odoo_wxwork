# -*- coding: utf-8 -*-
{
    "name": "Enterprise WeChat Message Push",
    "author": "RStudio",
    "website": "",
    "sequence": 1,
    "installable": True,
    "application": False,
    "auto_install": False,
    "category": "wxwork",
    "version": "13.0.0.1",
    "summary": """
        Odoo event notification to enterprise WeChat
        """,
    "description": """
功能：
====================

        """,
    "depends": [
        "mail",
        "mass_mailing",
        "wxwork_base",
        "wxwork_markdown_editor",
    ],
    "external_dependencies": {
        "python": ["html2text"],
    },
    "data": [
        # 'data/wxwork_data.xml',
        "wizard/message_template_preview_view.xml",
        "views/assets_templates.xml",
        "views/res_users_views.xml",
        "views/wxwork_message_template_views.xml",
        "views/res_config_settings_views.xml",
        "data/wxwork_message_data.xml",
        "security/ir.model.access.csv",
    ],
    "qweb": [
        "static/src/xml/*.xml",
    ],
    "post_init_hook": "_auto_install_lang",
    # 'external_dependencies': {'python': ['skimage']},
}
