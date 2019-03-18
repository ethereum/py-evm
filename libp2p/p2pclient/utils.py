from .exceptions import ControlFailure
from .pb import p2pd_pb2 as p2pd_pb


def raise_if_failed(response: p2pd_pb.Response) -> None:
    if response.type == p2pd_pb.Response.ERROR:
        raise ControlFailure(
            f"connect failed. msg={response.error.msg}"
        )
