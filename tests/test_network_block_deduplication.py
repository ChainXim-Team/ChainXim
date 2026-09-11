import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock

from miner.network_interface.nic_with_tp import NICWithTp
from network import INVMsg, Packet


class BlockRequestDeduplicationTest(unittest.TestCase):
    def test_block_is_requested_from_only_one_peer_while_in_flight(self):
        block = SimpleNamespace(name="B1")
        miner = SimpleNamespace(
            miner_id=0,
            has_received=MagicMock(return_value=False),
            receive=MagicMock(return_value=True),
        )
        nic = NICWithTp(miner)

        first = nic.reply_getdata(INVMsg(1, 0, block))
        duplicate = nic.reply_getdata(INVMsg(2, 0, block))
        nic.nic_receive(Packet(1, block))
        after_delivery = nic.reply_getdata(INVMsg(2, 0, block))

        self.assertTrue(first.isRequired)
        self.assertFalse(duplicate.isRequired)
        self.assertTrue(after_delivery.isRequired)

    def test_full_chain_request_authorizes_one_payload_inv_from_same_peer(self):
        block = SimpleNamespace(name="B1", parentblock=None, get_height=lambda: 1)
        local_tip = SimpleNamespace(get_height=lambda: 0)
        local_chain = SimpleNamespace(
            get_last_block=lambda: local_tip,
            search_block=lambda candidate: False,
        )
        miner = SimpleNamespace(
            miner_id=0,
            _isAdversary=False,
            has_received=MagicMock(return_value=False),
            get_local_chain=lambda: local_chain,
        )
        nic = NICWithTp(miner)
        nic._network = SimpleNamespace(withSegments=False)

        full_chain = nic.reply_getdata(INVMsg(1, 0, block, isFullChain=True))
        payload = nic.reply_getdata(INVMsg(1, 0, block))
        duplicate = nic.reply_getdata(INVMsg(2, 0, block))

        self.assertTrue(full_chain.isRequired)
        self.assertTrue(payload.isRequired)
        self.assertFalse(duplicate.isRequired)

    def test_duplicate_peer_cannot_consume_full_chain_authorization(self):
        block = SimpleNamespace(name="B1", parentblock=None, get_height=lambda: 1)
        local_tip = SimpleNamespace(get_height=lambda: 0)
        local_chain = SimpleNamespace(
            get_last_block=lambda: local_tip,
            search_block=lambda candidate: False,
        )
        miner = SimpleNamespace(
            miner_id=0,
            _isAdversary=False,
            has_received=MagicMock(return_value=False),
            get_local_chain=lambda: local_chain,
        )
        nic = NICWithTp(miner)
        nic._network = SimpleNamespace(withSegments=False)

        full_chain = nic.reply_getdata(INVMsg(1, 0, block, isFullChain=True))
        duplicate = nic.reply_getdata(INVMsg(2, 0, block))
        payload = nic.reply_getdata(INVMsg(1, 0, block))

        self.assertTrue(full_chain.isRequired)
        self.assertFalse(duplicate.isRequired)
        self.assertTrue(payload.isRequired)


if __name__ == "__main__":
    unittest.main()
