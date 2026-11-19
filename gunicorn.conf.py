access_log_format = '%(m)s %(s)s %(D)s'


def on_starting(server):
    from cutless_project.recovery_logging import FiltroRecuperacion

    server.log.error_log.addFilter(FiltroRecuperacion())
