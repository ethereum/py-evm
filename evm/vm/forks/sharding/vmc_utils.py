import json
import os


def get_smc_json():
    mydir = os.path.dirname(__file__)
    smc_path = os.path.join(mydir, 'contracts/validator_manager.json')
    smc_json_str = open(smc_path).read()
    return json.loads(smc_json_str)
