import factory

from cancel_token import CancelToken


class CancelTokenFactory(factory.Factory):
    class Meta:
        model = CancelToken

    name = factory.Sequence(lambda n: "test-token-{}".format(n))
