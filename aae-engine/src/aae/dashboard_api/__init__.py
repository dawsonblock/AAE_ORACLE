__all__ = ['create_app']


def create_app(*args, **kwargs):
    from aae.dashboard_api.server import create_app as _create_app

    return _create_app(*args, **kwargs)
