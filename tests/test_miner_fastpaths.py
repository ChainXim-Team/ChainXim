import unittest
from array import array
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, mock_open, patch

from consensus import FastPoW, PoW, VirtualPoW
from miner.miner import Miner


class _ClearSpy(list):
    def __init__(self, values=()):
        super().__init__(values)
        self.clear_calls = 0

    def clear(self):
        self.clear_calls += 1
        super().clear()


class MinerBackboneFastPathTest(unittest.TestCase):
    def make_miner(self, q=1, max_block_capacity=0, consensus_type=FastPoW):
        miner = Miner.__new__(Miner)
        consensus = consensus_type.__new__(consensus_type)
        consensus.q = q
        consensus.receive_tape = []
        consensus.local_state_update = MagicMock(return_value=(None, [], []))
        miner.consensus = consensus
        miner._skip_pow_consensus = isinstance(consensus, PoW) and q == 0
        miner.max_block_capacity = max_block_capacity
        miner.requires_input_tape = max_block_capacity > 0 or not miner._skip_pow_consensus
        miner.input_tape = []
        miner._NIC = SimpleNamespace(_receive_buffer=[])
        miner.forward = MagicMock()
        miner.launch_consensus = MagicMock(return_value=(None, False))
        return miner

    def construct_miner(self, consensus, max_block_capacity=0):
        constructor = lambda miner_id, consensus_params, chain_factory: consensus
        with (
            patch("miner.miner.for_name", return_value=constructor),
            patch("miner.miner.global_var.get_consensus_type", return_value="unused"),
            patch("miner.miner.global_var.get_chain_data_path", return_value=Path("/unused")),
            patch("builtins.open", mock_open()),
        ):
            return Miner(0, {}, max_block_capacity)

    def test_zero_hashpower_detection_applies_to_pow_subclasses(self):
        for consensus_type in (PoW, VirtualPoW, FastPoW):
            with self.subTest(consensus_type=consensus_type.__name__):
                consensus = consensus_type.__new__(consensus_type)
                consensus.q = 0

                miner = self.construct_miner(consensus)

                self.assertTrue(miner._skip_pow_consensus)
                self.assertFalse(miner.requires_input_tape)

    def test_zero_q_non_pow_consensus_is_not_skipped(self):
        miner = self.construct_miner(SimpleNamespace(q=0))

        self.assertFalse(miner._skip_pow_consensus)
        self.assertTrue(miner.requires_input_tape)

    def test_empty_receive_tape_skips_local_state_update(self):
        miner = self.make_miner(q=1)
        miner.input_tape.append(("INSERT", b"payload"))

        miner.BackboneProtocol(7)

        miner.consensus.local_state_update.assert_not_called()
        miner.launch_consensus.assert_called_once_with(b"payload", 7)

    def test_nonempty_receive_tape_still_updates_local_state(self):
        miner = self.make_miner(q=1)
        miner.consensus.receive_tape.append(object())
        miner.input_tape.append(("INSERT", b"payload"))

        miner.BackboneProtocol(7)

        miner.consensus.local_state_update.assert_called_once_with()

    def test_zero_hashpower_pow_skips_input_and_consensus(self):
        miner = self.make_miner(q=0, consensus_type=PoW)

        with patch("miner.miner.I") as input_function:
            result = miner.BackboneProtocol(7)

        self.assertIsNone(result)
        self.assertFalse(miner.requires_input_tape)
        input_function.assert_not_called()
        miner.launch_consensus.assert_not_called()

    def test_dataitem_mode_keeps_zero_hashpower_input_processing(self):
        miner = self.make_miner(q=0, max_block_capacity=1, consensus_type=PoW)
        miner.dataitem_queue = array('Q')
        miner.input_tape.append(("INSERT", array('Q', [1]).tobytes()))

        miner.BackboneProtocol(7)

        self.assertTrue(miner.requires_input_tape)
        self.assertEqual(miner.dataitem_queue.tolist(), [1])
        miner.launch_consensus.assert_not_called()

    def test_clear_tapes_only_clears_nonempty_tapes(self):
        miner = self.make_miner()
        miner.input_tape = _ClearSpy()
        miner.consensus.receive_tape = _ClearSpy([object()])
        miner._NIC._receive_buffer = _ClearSpy()

        miner.clear_tapes()

        self.assertEqual(miner.input_tape.clear_calls, 0)
        self.assertEqual(miner.consensus.receive_tape.clear_calls, 1)
        self.assertEqual(miner._NIC._receive_buffer.clear_calls, 0)
        self.assertFalse(miner.consensus.receive_tape)


if __name__ == "__main__":
    unittest.main()
