import json
import os
import urllib.request

from commands import admin, profile, register, roster

DISPATCH = {
    "register":    register.handle,
    "setclasses":  register.handle_classes,
    "update":      register.handle_update,
    "unregister":  register.handle_unregister,
    "profile":     profile.handle,
    "lookup":      profile.handle_lookup,
    "roster":      roster.handle,
    "adminset":    admin.handle_set,
    "adminremove": admin.handle_remove,
}


def post_followup(app_id, token, data):
    url = f"https://discord.com/api/v10/webhooks/{app_id}/{token}/messages/@original"
    req = urllib.request.Request(
        url, data=json.dumps(data).encode(), method="PATCH",
        headers={"Content-Type": "application/json"},
    )
    urllib.request.urlopen(req)


def handler(event, context):
    command_name = event["data"]["name"]
    handler_fn = DISPATCH.get(command_name)
    response_data = (handler_fn(event) if handler_fn
                     else {"content": f"Unknown command: `{command_name}`"})
    post_followup(event["application_id"], event["token"], response_data)
