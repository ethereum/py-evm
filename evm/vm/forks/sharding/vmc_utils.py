import json
import os


def get_vmc_json():
    mydir = os.path.dirname(__file__)
    vmc_path = os.path.join(mydir, 'contracts/validator_manager.json')
    vmc_json_str = open(vmc_path).read()
    return json.loads(vmc_json_str)
