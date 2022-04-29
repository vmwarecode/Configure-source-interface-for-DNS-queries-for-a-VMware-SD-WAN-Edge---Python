#!/usr/bin/env/python3

import os
from uuid import uuid4
from client import *
from copy import deepcopy

# EDIT THESE!
HOST = os.environ["VCO_HOST"]
USERNAME = os.environ["VCO_USERNAME"]
PASSWORD = os.environ["VCO_PASSWORD"]
NO_VERIFY_SSL = bool(os.environ.get("NO_VERIFY_SSL"))
IS_OPERATOR_USER = bool(os.environ.get("IS_OPERATOR_USER"))
ENTERPRISE_ID = 129
EDGE_ID = 388

def copy_profile_dns_refs_to_edge_for_segment(profile_device_settings, edge_specific_device_settings, target_segment):

    edge_specific_device_settings_refs = edge_specific_device_settings["refs"]
    profile_device_settings_refs = profile_device_settings["refs"]

    for ref_type in ["deviceSettings:dns:primaryProvider", "deviceSettings:dns:backupProvider", "deviceSettings:dns:privateProviders"]:
        if ref_type not in edge_specific_device_settings_refs:
            edge_specific_device_settings_refs[ref_type] = []
        elif not isinstance(edge_specific_device_settings_refs[ref_type], list):
            edge_specific_device_settings_refs[ref_type] = [edge_specific_device_settings_refs[ref_type]]

        if ref_type in profile_device_settings_refs:
            refs_of_type = profile_device_settings_refs[ref_type]
            profile_refs_of_type_as_list = refs_of_type if isinstance(refs_of_type, list) else [refs_of_type]
            for src_ref in [r for r in profile_refs_of_type_as_list if r["segmentLogicalId"] == target_segment["logicalId"]]:
                new_ref = deepcopy(src_ref)
                new_ref["configurationId"] = edge_specific_device_settings["configurationId"]
                new_ref["moduleId"] = edge_specific_device_settings["id"]
                edge_specific_device_settings_refs[ref_type].append(new_ref)

def main():
    client = VcoRequestManager(HOST, verify_ssl=not NO_VERIFY_SSL)
    client.authenticate(USERNAME, PASSWORD, is_operator=IS_OPERATOR_USER)

    print("### GETTING EDGE CONFIGURATION STACK ###")
    params = { "enterpriseId": ENTERPRISE_ID,
               "edgeId": EDGE_ID }
    try:
        config_stack = client.call_api("edge/getEdgeConfigurationStack", params)
    except ApiException as e:
        print(e)

    # The Edge-specific profile is always the first entry, convert to a dict for easy manipulation
    edge_specific_profile = config_stack[0]
    edge_specific_device_settings = [m for m in edge_specific_profile["modules"] if m["name"] == "deviceSettings"][0]
    edge_specific_device_settings_data = edge_specific_device_settings["data"]

    profile = config_stack[1]
    profile_device_settings = [m for m in profile["modules"] if m["name"] == "deviceSettings"][0]
    profile_device_settings_data = profile_device_settings["data"]

    network_segments = profile_device_settings["refs"]["deviceSettings:segment"]

    for idx, edge_device_settings_segment_details in enumerate(edge_specific_device_settings_data["segments"]):
        profile_device_settings_segment_details = profile_device_settings_data["segments"][idx]
        if "dns" not in edge_device_settings_segment_details or not edge_device_settings_segment_details["dns"].get("override", False):
            edge_device_settings_segment_details["dns"] = deepcopy(profile_device_settings_segment_details["dns"])
        edge_device_settings_segment_details["dns"]["override"] = True
        edge_device_settings_segment_details["dns"]["sourceInterface"] = "GE2"

        current_segment = [segment for segment in network_segments if segment["data"]["segmentId"] == edge_device_settings_segment_details["segment"]["segmentId"]][0]
        copy_profile_dns_refs_to_edge_for_segment(profile_device_settings, edge_specific_device_settings, current_segment)

    print("### UPDATING EDGE DEVICE SETTINGS ###")
    try:
        client.call_api("configuration/updateConfigurationModule", {
            "enterpriseId": ENTERPRISE_ID,
            "configurationModuleId": edge_specific_device_settings["id"],
            "_update": {
                "data":  edge_specific_device_settings_data,
                "refs":  edge_specific_device_settings["refs"]
            }
        })
        print("Successfully updated configuration.")
    except ApiException as e:
        print(e)

if __name__ == "__main__":
    main()