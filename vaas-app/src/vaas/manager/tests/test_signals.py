# -*- coding: utf-8 -*-

from nose.tools import assert_equals
from mock import Mock, call, patch, MagicMock
from django.conf import settings

from vaas.manager.models import Director, Backend, Probe
from vaas.cluster.models import Dc, LogicalCluster
from vaas.manager.signals import switch_state_and_reload, regenerate_and_reload_vcl, vcl_update


def test_switch_state_and_reload_cluster_filter_for_backend():
    cluster1 = LogicalCluster.objects.create(name="first cluster")
    # Created, but not used, just to check if cluster filtering works.
    LogicalCluster.objects.create(name="second cluster")
    dc1 = Dc.objects.create(symbol='dc1', name='First datacenter')
    probe = Probe.objects.create(name='default_probe', url='/ts.1')
    director1 = Director.objects.create(
        name='first_service',
        route_expression='/first',
        mode='random',
        probe=probe
    )
    backend1 = Backend.objects.create(
        dc=dc1,
        director=director1,
        address='192.168.200.10',
        port=8080,
        weight=1
    )
    director1.cluster.add(cluster1)

    queryset = Backend.objects.all().filter(id=backend1.id)
    queryset.update = Mock()

    with patch(
        'vaas.manager.signals.regenerate_and_reload_vcl',
        return_value=None
    ) as regenerate_and_reload_vcl_mock:

        switch_state_and_reload(queryset, True)
        assert_equals(
            [call(enabled=True)],
            queryset.update.call_args_list
        )
        assert_equals(
            [call([cluster1])],
            regenerate_and_reload_vcl_mock.call_args_list
        )


def test_switch_state_and_reload_with_empty_list():
    queryset = MagicMock()
    queryset.update = Mock()
    with patch(
        'vaas.manager.signals.regenerate_and_reload_vcl',
        return_value=None
    ) as regenerate_and_reload_vcl_mock:

        switch_state_and_reload(queryset, True)
        assert_equals([call(enabled=True)], queryset.update.call_args_list)
        """
        shouldn't refresh any cluster, because of empty list
        """
        assert_equals([call([])], regenerate_and_reload_vcl_mock.call_args_list)


def test_regenerate_and_reload_vcl_if_can_obtain_request():
    request = MagicMock(id=10)

    with patch('vaas.manager.signals.get_current_request', return_value=request):
        with patch(
            'vaas.manager.signals.VclRefreshState.set_refresh',
            return_value=None
        ) as vcl_refresh_mock:

            clusters = []
            regenerate_and_reload_vcl(clusters)
            assert_equals(
                [call(request.id, [])],
                vcl_refresh_mock.call_args_list
            )


def test_regenerate_and_reload_vcl_if_cannot_obtain_request():
    with patch('vaas.manager.signals.get_current_request', return_value=None):
        with patch(
            'vaas.manager.signals.VclRefreshState.set_refresh',
            return_value=None
        ) as vcl_refresh_mock:

            clusters = []
            regenerate_and_reload_vcl(clusters)
            assert_equals([], vcl_refresh_mock.call_args_list)


def test_vcl_update_if_sender_allowed():
    settings.SIGNALS = 'on'

    probe1 = Probe.objects.create(name='test_probe', url='/status')
    director1 = Director.objects.create(
        name='first_service',
        router='req.url',
        route_expression='/first',
        probe=probe1,
        active_active=False,
        mode='round-robin',
        remove_path=False
    )

    with patch('vaas.manager.signals.regenerate_and_reload_vcl', return_value=None) as regenerate_and_reload_vcl_mock:
        kwargs = {'instance': director1}
        vcl_update(Director, **kwargs)
        assert_equals([call([])], regenerate_and_reload_vcl_mock.call_args_list)

    settings.SIGNALS = 'off'


def test_vcl_update_cluster_filter_for_director():
    settings.SIGNALS = 'on'

    cluster1 = LogicalCluster.objects.create(name="first cluster")
    """
    Created, but not used, just to check if cluster filtering works.
    """
    LogicalCluster.objects.create(name="second cluster")

    probe1 = Probe.objects.create(name='test_probe', url='/status')
    director1 = Director.objects.create(
        name='first_service',
        router='req.url',
        route_expression='/first',
        probe=probe1,
        active_active=False,
        mode='round-robin',
        remove_path=False,
    )
    director1.cluster.add(cluster1)

    with patch('vaas.manager.signals.regenerate_and_reload_vcl', return_value=None) as regenerate_and_reload_vcl_mock:
        kwargs = {'instance': director1}
        vcl_update(Director, **kwargs)
        assert_equals([call([cluster1])], regenerate_and_reload_vcl_mock.call_args_list)

    settings.SIGNALS = 'off'


def test_vcl_update_if_sender_not_allowed():
    settings.SIGNALS = 'on'
    with patch('vaas.manager.signals.regenerate_and_reload_vcl', return_value=None) as regenerate_and_reload_vcl_mock:
        vcl_update(None)
        assert_equals([], regenerate_and_reload_vcl_mock.call_args_list)
    settings.SIGNALS = 'off'
