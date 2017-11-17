import os
import json

from jsonschema import (
    validate
)
from evm.exceptions import (
    ValidationError
)

class Package(object):
    def __init__(self, package_identifier):
        if not os.path.exists(package_identifier):
            raise ValidationError

        self.package_identifier = package_identifier

        schema_data = json.load(open('./ethpm/schema.json'))
        package_data = json.load(open(package_identifier))

        validate(package_data, schema_data)
        self.parsed_json = package_data
