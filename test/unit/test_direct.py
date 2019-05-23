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


from __future__ import print_function

from unittest import TestCase
from threading import Thread, Event

from neobolt.direct import Connection, ConnectionPool
from neobolt.exceptions import ClientError, ServiceUnavailable


class FakeSocket(object):
    def __init__(self, address):
        self.address = address

    def getpeername(self):
        return self.address

    def sendall(self, data):
        return

    def close(self):
        return


class QuickConnection(object):

    def __init__(self, socket):
        self.socket = socket
        self.address = socket.getpeername()

    def reset(self):
        pass

    def close(self):
        self.socket.close()

    def closed(self):
        return False

    def defunct(self):
        return False

    def timedout(self):
        return False


def connector(address, **kwargs):
    return QuickConnection(FakeSocket(address))


class ConnectionTestCase(TestCase):

    def test_conn_timedout(self):
        address = ("127.0.0.1", 7687)
        connection = Connection(1, address, FakeSocket(address),
                                max_connection_lifetime=0)
        self.assertEqual(connection.timedout(), True)

    def test_conn_not_timedout_if_not_enabled(self):
        address = ("127.0.0.1", 7687)
        connection = Connection(1, address, FakeSocket(address),
                                max_connection_lifetime=-1)
        self.assertEqual(connection.timedout(), False)

    def test_conn_not_timedout(self):
        address = ("127.0.0.1", 7687)
        connection = Connection(1, address, FakeSocket(address),
                                max_connection_lifetime=999999999)
        self.assertEqual(connection.timedout(), False)


class ConnectionPoolTestCase(TestCase):

    def setUp(self):
        self.pool = ConnectionPool(connector, ("127.0.0.1", 7687))

    def tearDown(self):
        self.pool.close()

    def assert_pool_size(self, address, expected_active, expected_inactive, pool=None):
        if pool is None:
            pool = self.pool
        try:
            connections = pool.connections[address]
        except KeyError:
            self.assertEqual(0, expected_active)
            self.assertEqual(0, expected_inactive)
        else:
            self.assertEqual(expected_active, len([cx for cx in connections if cx.in_use]))
            self.assertEqual(expected_inactive, len([cx for cx in connections if not cx.in_use]))

    def test_can_acquire(self):
        address = ("127.0.0.1", 7687)
        connection = self.pool.acquire_direct(address)
        assert connection.address == address
        self.assert_pool_size(address, 1, 0)

    def test_can_acquire_twice(self):
        address = ("127.0.0.1", 7687)
        connection_1 = self.pool.acquire_direct(address)
        connection_2 = self.pool.acquire_direct(address)
        assert connection_1.address == address
        assert connection_2.address == address
        assert connection_1 is not connection_2
        self.assert_pool_size(address, 2, 0)

    def test_can_acquire_two_addresses(self):
        address_1 = ("127.0.0.1", 7687)
        address_2 = ("127.0.0.1", 7474)
        connection_1 = self.pool.acquire_direct(address_1)
        connection_2 = self.pool.acquire_direct(address_2)
        assert connection_1.address == address_1
        assert connection_2.address == address_2
        self.assert_pool_size(address_1, 1, 0)
        self.assert_pool_size(address_2, 1, 0)

    def test_can_acquire_and_release(self):
        address = ("127.0.0.1", 7687)
        connection = self.pool.acquire_direct(address)
        self.assert_pool_size(address, 1, 0)
        self.pool.release(connection)
        self.assert_pool_size(address, 0, 1)

    def test_releasing_twice(self):
        address = ("127.0.0.1", 7687)
        connection = self.pool.acquire_direct(address)
        self.pool.release(connection)
        self.assert_pool_size(address, 0, 1)
        self.pool.release(connection)
        self.assert_pool_size(address, 0, 1)

    def test_cannot_acquire_after_close(self):
        with ConnectionPool(lambda a: QuickConnection(FakeSocket(a)),
                            ()) as pool:
            pool.close()
            with self.assertRaises(ServiceUnavailable):
                _ = pool.acquire_direct("X")

    def test_in_use_count(self):
        address = ("127.0.0.1", 7687)
        self.assertEqual(self.pool.in_use_connection_count(address), 0)
        connection = self.pool.acquire_direct(address)
        self.assertEqual(self.pool.in_use_connection_count(address), 1)
        self.pool.release(connection)
        self.assertEqual(self.pool.in_use_connection_count(address), 0)

    def test_max_conn_pool_size(self):
        with ConnectionPool(connector, (), max_connection_pool_size=1,
                            connection_acquisition_timeout=0) as pool:
            address = ("127.0.0.1", 7687)
            pool.acquire_direct(address)
            self.assertEqual(pool.in_use_connection_count(address), 1)
            with self.assertRaises(ClientError):
                pool.acquire_direct(address)
            self.assertEqual(pool.in_use_connection_count(address), 1)

    def test_multithread(self):
        with ConnectionPool(connector, (), max_connection_pool_size=5,
                            connection_acquisition_timeout=10) as pool:
            address = ("127.0.0.1", 7687)
            releasing_event = Event()

            # We start 10 threads to compete connections from pool with size of 5
            threads = []
            for i in range(10):
                t = Thread(target=acquire_release_conn, args=(pool, address, releasing_event))
                t.start()
                threads.append(t)

            # The pool size should be 5, all are in-use
            self.assert_pool_size(address, 5, 0, pool)
            # Now we allow thread to release connections they obtained from pool
            releasing_event.set()

            # wait for all threads to release connections back to pool
            for t in threads:
                t.join()
            # The pool size is still 5, but all are free
            self.assert_pool_size(address, 0, 5, pool)


def acquire_release_conn(pool, address, releasing_event):
    conn = pool.acquire_direct(address)
    releasing_event.wait()
    pool.release(conn)