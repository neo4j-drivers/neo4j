#!/usr/bin/env python
# -*- encoding: utf-8 -*-

# Copyright (c) 2002-2019 "Neo4j,"
# Neo4j Sweden AB [http://neo4j.com]
#
# This file is part of Neo4j.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


from pytest import raises

from neobolt.direct import connect, Connection
from neobolt.exceptions import ServiceUnavailable, IncompleteCommitError, \
    DatabaseUnavailableError
from test.stub.tools import StubCluster


class FakeConnectionPool(object):

    def __init__(self):
        self.deactivated_addresses = []

    def deactivate(self, address):
        self.deactivated_addresses.append(address)


def test_construction():
    with StubCluster({9001: "v3/empty.script"}):
        address = ("127.0.0.1", 9001)
        with connect(address) as cx:
            assert isinstance(cx, Connection)


def test_return_1():
    with StubCluster({9001: "v3/return_1.script"}):
        address = ("127.0.0.1", 9001)
        with connect(address) as cx:
            metadata = {}
            records = []
            cx.run("RETURN $x", {"x": 1}, on_success=metadata.update)
            cx.pull_all(on_success=metadata.update, on_records=records.extend)
            cx.send_all()
            cx.fetch_all()
            assert records == [[1]]


def test_return_1_as_read():
    with StubCluster({9001: "v3/return_1_as_read.script"}):
        address = ("127.0.0.1", 9001)
        with connect(address) as cx:
            metadata = {}
            records = []
            cx.run("RETURN $x", {"x": 1}, mode="r", on_success=metadata.update)
            cx.pull_all(on_success=metadata.update, on_records=records.extend)
            cx.send_all()
            cx.fetch_all()
            assert records == [[1]]


def test_return_1_in_tx():
    with StubCluster({9001: "v3/return_1_in_tx.script"}):
        address = ("127.0.0.1", 9001)
        with connect(address) as cx:
            metadata = {}
            records = []
            cx.begin(on_success=metadata.update)
            cx.run("RETURN $x", {"x": 1}, on_success=metadata.update)
            cx.pull_all(on_success=metadata.update, on_records=records.extend)
            cx.commit(on_success=metadata.update)
            cx.send_all()
            cx.fetch_all()
            assert records == [[1]]
            assert {"fields": ["x"], "bookmark": "bookmark:1"} == metadata


def test_return_1_in_tx_as_read():
    with StubCluster({9001: "v3/return_1_in_tx_as_read.script"}):
        address = ("127.0.0.1", 9001)
        with connect(address) as cx:
            metadata = {}
            records = []
            cx.begin(on_success=metadata.update)
            cx.run("RETURN $x", {"x": 1}, mode="r", on_success=metadata.update)
            cx.pull_all(on_success=metadata.update, on_records=records.extend)
            cx.commit(on_success=metadata.update)
            cx.send_all()
            cx.fetch_all()
            assert records == [[1]]
            assert {"fields": ["x"], "bookmark": "bookmark:1"} == metadata


def test_begin_with_metadata():
    with StubCluster({9001: "v3/begin_with_metadata.script"}):
        address = ("127.0.0.1", 9001)
        with connect(address) as cx:
            metadata = {}
            records = []
            cx.begin(metadata={"mode": "r"}, on_success=metadata.update)
            cx.run("RETURN $x", {"x": 1}, on_success=metadata.update)
            cx.pull_all(on_success=metadata.update, on_records=records.extend)
            cx.commit(on_success=metadata.update)
            cx.send_all()
            cx.fetch_all()
            assert records == [[1]]
            assert {"fields": ["x"], "bookmark": "bookmark:1"} == metadata


def test_begin_with_timeout():
    with StubCluster({9001: "v3/begin_with_timeout.script"}):
        address = ("127.0.0.1", 9001)
        with connect(address) as cx:
            metadata = {}
            records = []
            cx.begin(timeout=12.34, on_success=metadata.update)
            cx.run("RETURN $x", {"x": 1}, on_success=metadata.update)
            cx.pull_all(on_success=metadata.update, on_records=records.extend)
            cx.commit(on_success=metadata.update)
            cx.send_all()
            cx.fetch_all()
            assert records == [[1]]
            assert {"fields": ["x"], "bookmark": "bookmark:1"} == metadata


def test_run_with_bookmarks():
    with StubCluster({9001: "v3/run_with_bookmarks.script"}):
        address = ("127.0.0.1", 9001)
        with connect(address) as cx:
            metadata = {}
            records = []
            cx.run("RETURN $x", {"x": 1}, bookmarks=["foo", "bar"],
                   on_success=metadata.update)
            cx.pull_all(on_success=metadata.update, on_records=records.extend)
            cx.send_all()
            cx.fetch_all()
            assert records == [[1]]


def test_run_with_metadata():
    with StubCluster({9001: "v3/run_with_metadata.script"}):
        address = ("127.0.0.1", 9001)
        with connect(address) as cx:
            metadata = {}
            records = []
            cx.run("RETURN $x", {"x": 1}, metadata={"mode": "r"},
                   on_success=metadata.update)
            cx.pull_all(on_success=metadata.update, on_records=records.extend)
            cx.send_all()
            cx.fetch_all()
            assert records == [[1]]


def test_run_with_timeout():
    with StubCluster({9001: "v3/run_with_timeout.script"}):
        address = ("127.0.0.1", 9001)
        with connect(address) as cx:
            metadata = {}
            records = []
            cx.run("RETURN $x", {"x": 1}, timeout=12.34,
                   on_success=metadata.update)
            cx.pull_all(on_success=metadata.update, on_records=records.extend)
            cx.send_all()
            cx.fetch_all()
            assert records == [[1]]


def test_disconnect_on_run():
    with StubCluster({9001: "v3/disconnect_on_run.script"}):
        address = ("127.0.0.1", 9001)
        with connect(address) as cx:
            with raises(ServiceUnavailable):
                metadata = {}
                cx.run("RETURN $x", {"x": 1}, on_success=metadata.update)
                cx.send_all()
                cx.fetch_all()


def test_disconnect_on_pull_all():
    with StubCluster({9001: "v3/disconnect_on_pull_all.script"}):
        address = ("127.0.0.1", 9001)
        with connect(address) as cx:
            with raises(ServiceUnavailable):
                metadata = {}
                records = []
                cx.run("RETURN $x", {"x": 1}, on_success=metadata.update)
                cx.pull_all(on_success=metadata.update,
                            on_records=records.extend)
                cx.send_all()
                cx.fetch_all()


def test_disconnect_after_init():
    with StubCluster({9001: "v3/disconnect_after_init.script"}):
        address = ("127.0.0.1", 9001)
        with connect(address) as cx:
            with raises(ServiceUnavailable):
                metadata = {}
                cx.run("RETURN $x", {"x": 1}, on_success=metadata.update)
                cx.send_all()
                cx.fetch_all()


def test_fail_on_commit():
    with StubCluster({9001: "v3/fail_on_commit.script"}):
        address = ("127.0.0.1", 9001)
        with connect(address) as cx:
            metadata = {}
            records = []
            cx.begin(on_success=metadata.update)
            cx.run("CREATE (a) RETURN id(a)", on_success=metadata.update)
            cx.pull_all(on_success=metadata.update, on_records=records.extend)
            cx.send_all()
            cx.fetch_all()
            cx.commit(on_success=metadata.update)
            with raises(ServiceUnavailable):
                cx.send_all()
                cx.fetch_all()


def test_connection_error_on_commit():
    with StubCluster({9001: "v3/connection_error_on_commit.script"}):
        address = ("127.0.0.1", 9001)
        with connect(address) as cx:
            metadata = {}
            records = []
            cx.begin(on_success=metadata.update)
            cx.run("CREATE (a) RETURN id(a)", on_success=metadata.update)
            cx.pull_all(on_success=metadata.update, on_records=records.extend)
            cx.send_all()
            cx.fetch_all()
            cx.commit(on_success=metadata.update)
            with raises(IncompleteCommitError):
                cx.send_all()
                cx.fetch_all()


def test_address_deactivation_on_database_unavailable_error():
    with StubCluster({9001: "v3/database_unavailable.script"}):
        address = ("127.0.0.1", 9001)
        with connect(address) as cx:
            cx.pool = FakeConnectionPool()
            with raises(DatabaseUnavailableError):
                metadata = {}
                cx.run("RETURN 1", {}, on_success=metadata.update)
                cx.pull_all()
                cx.send_all()
                cx.fetch_all()
            assert ("127.0.0.1", 9001) in cx.pool.deactivated_addresses
