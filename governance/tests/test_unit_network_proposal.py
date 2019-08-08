import hashlib
import random
import sys
import unittest
from copy import deepcopy
from json import dumps, loads
from unittest.mock import patch, Mock

from iconservice import *
from tbears.libs.scoretest.score_test_case import Address

from governance.network_proposal import NetworkProposal, ProposalInfo, NetworkProposalVote, NetworkProposalStatus, \
    NetworkProposalType

DATA_BYTE_ORDER = 'big'  # big endian
COUNT_OF_MAIN_PREPS = 22
DEFAULT_DELEGATED = 10

PATCHER_ARRAY_DB = patch('governance.network_proposal.ArrayDB')
PATCHER_DICT_DB = patch('governance.network_proposal.DictDB')
PATCHER_JSON_LOADS = patch('governance.network_proposal.json_loads', side_effect=loads)
PATCHER_JSON_DUMPS = patch('governance.network_proposal.json_dumps', side_effect=dumps)
PATCHER_CHECK_VOTE_RESULT = patch('governance.network_proposal.NetworkProposal._check_vote_result', return_value=True)
PATCHER_CHECK_REGISTERED_PROPOSAL = patch('governance.network_proposal.NetworkProposal._check_registered_proposal',
                                          return_value=False)
PATCHER_VALIDATE_PROPOSAL = patch('governance.network_proposal.NetworkProposal._validate_proposal', return_value=True)
PATCHER_VALIDATE_TEXT_PROPOSAL = patch('governance.network_proposal.NetworkProposal._validate_text_proposal',
                                       return_value=True)
PATCHER_VALIDATE_REVISION_PROPOSAL = patch('governance.network_proposal.NetworkProposal._validate_revision_proposal',
                                           return_value=True)
PATCHER_VALIDATE_MALICIOUS_SCORE_PROPOSAL = patch(
    'governance.network_proposal.NetworkProposal._validate_malicious_score_proposal', return_value=True)
PATCHER_VALIDATE_PREP_DISQUALIFICATION_PROPOSAL = patch(
    'governance.network_proposal.NetworkProposal._validate_prep_disqualification_proposal', return_value=True)
PATCHER_VALIDATE_STEP_PRICE_PROPOSAL = patch(
    'governance.network_proposal.NetworkProposal._validate_step_price_proposal', return_value=True)


def create_tx_hash(data: bytes = None) -> bytes:
    if data is None:
        max_int = sys.maxsize
        length = (max_int.bit_length() + 7) // 8
        data = int(random.randint(0, max_int)).to_bytes(length, DATA_BYTE_ORDER)
    return hashlib.sha3_256(data).digest()


def create_address(prefix: int = 0, data: bytes = None) -> 'Address':
    if data is None:
        data = create_tx_hash()
    hash_value = hashlib.sha3_256(data).digest()
    return Address(AddressPrefix(prefix), hash_value[-20:])


def start_patches(*args):
    for patcher in args:
        patcher.start()


def stop_patches(*args):
    for patcher in args:
        patcher.stop()


def patch_several(*decorate_args):
    def decorate(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_patches(*decorate_args)
            ret = func(*args, **kwargs)
            stop_patches(*decorate_args)
            return ret

        return wrapper

    return decorate


class Prep:
    def __init__(self, address: Address, delegated: int):
        self.address = address
        self.delegated = delegated


class TestUnitNetworkProposal(unittest.TestCase):

    @patch_several(PATCHER_ARRAY_DB, PATCHER_DICT_DB)
    def setUp(self) -> None:
        db = Mock()
        db.__class = IconScoreDatabase
        self.network_proposal = NetworkProposal(db)
        self.network_proposal._proposal_list = {}
        self.network_proposal._proposal_list_keys = []

    @patch_several(PATCHER_JSON_LOADS, PATCHER_JSON_DUMPS)
    def test_proposal_info_to_bytes_from_bytes(self):
        voter = self._generate_voter(1, 100, 2, 200, 3000)
        proposal_info, self.network_proposal._proposal_list[proposal_info.id] = self._generate_proposal_info(
            NetworkProposalStatus.VOTING, voter)
        proposal_info_in_bytes = proposal_info.to_bytes()

        expected_value = {
            "id": proposal_info.id,
            "proposer": str(proposal_info.proposer),
            "description": proposal_info.description,
            "type": proposal_info.type,
            "value": proposal_info.value,
            "start_block_height": proposal_info.start_block_height,
            "end_block_height": proposal_info.end_block_height,
            "status": proposal_info.status,
            "voter": voter
        }

        self.assertEqual(proposal_info_in_bytes, dumps(expected_value).encode())
        self.assertEqual(proposal_info_in_bytes, proposal_info.from_bytes(proposal_info_in_bytes).to_bytes())

    @patch_several(PATCHER_VALIDATE_TEXT_PROPOSAL, PATCHER_VALIDATE_REVISION_PROPOSAL,
                   PATCHER_VALIDATE_MALICIOUS_SCORE_PROPOSAL, PATCHER_VALIDATE_PREP_DISQUALIFICATION_PROPOSAL,
                   PATCHER_VALIDATE_STEP_PRICE_PROPOSAL)
    def test_validate_proposal(self):
        value_of_type_0 = {"text": "text"}
        value_of_type_1 = {"code": hex(0), "name": "1.1.0"}
        value_of_type_2 = {"address": str(create_address()), "type": hex(0)}
        value_of_type_3 = {"address": str(create_address())}
        value_of_type_4 = {"value": hex(0)}

        self.network_proposal._validate_func = [self.network_proposal._validate_text_proposal,
                                                self.network_proposal._validate_revision_proposal,
                                                self.network_proposal._validate_malicious_score_proposal,
                                                self.network_proposal._validate_prep_disqualification_proposal,
                                                self.network_proposal._validate_step_price_proposal]
        return_value = self.network_proposal._validate_proposal(0, value_of_type_0)
        assert self.network_proposal._validate_text_proposal.called and return_value

        return_value = self.network_proposal._validate_proposal(1, value_of_type_1)
        assert self.network_proposal._validate_revision_proposal.called and return_value

        return_value = self.network_proposal._validate_proposal(2, value_of_type_2)
        assert self.network_proposal._validate_malicious_score_proposal.called and return_value

        return_value = self.network_proposal._validate_proposal(3, value_of_type_3)
        assert self.network_proposal._validate_prep_disqualification_proposal.called and return_value

        return_value = self.network_proposal._validate_proposal(4, value_of_type_4)
        assert self.network_proposal._validate_step_price_proposal.called and return_value

    def test_validate_text_proposal(self):
        value_of_type_0 = {"text": "text"}
        assert self.network_proposal._validate_text_proposal(value_of_type_0)

    def test_validate_revision_proposal(self):
        value_of_type_1 = {"code": hex(0), "name": "1.1.0"}
        assert self.network_proposal._validate_revision_proposal(value_of_type_1)

    @patch('governance.network_proposal.Address.is_contract', return_value=True)
    def test_validate_malicious_score_proposal(self, is_contract):
        value_of_type_2 = {"address": str(create_address()), "type": hex(0)}
        assert self.network_proposal._validate_malicious_score_proposal(value_of_type_2)

    def test_validate_prep_disqualification_proposal(self):
        main_prep = [Prep(create_address(), 0) for _ in range(COUNT_OF_MAIN_PREPS)]
        sub_prep = [Prep(create_address(), 0) for _ in range(COUNT_OF_MAIN_PREPS, 100)]

        with patch('governance.network_proposal.get_main_prep_info', return_value=(main_prep, None)):
            with patch('governance.network_proposal.get_sub_prep_info', return_value=(sub_prep, None)):
                value_of_type_3 = {"address": str(main_prep[0].address)}
                assert self.network_proposal._validate_prep_disqualification_proposal(value_of_type_3)
                value_of_type_3 = {"address": str(sub_prep[0].address)}
                assert self.network_proposal._validate_prep_disqualification_proposal(value_of_type_3)
                value_of_type_3 = {"address": str(create_address())}
                assert not self.network_proposal._validate_prep_disqualification_proposal(value_of_type_3)

    def test_validate_step_price_proposal(self):
        value_of_type_4 = {"value": hex(0)}
        assert self.network_proposal._validate_step_price_proposal(value_of_type_4)

    @patch_several(PATCHER_JSON_LOADS, PATCHER_JSON_DUMPS)
    def test_check_registered_proposal(self):
        tx_hash = create_tx_hash()
        self.assertRaises(KeyError, self.network_proposal._check_registered_proposal, tx_hash)

        self.network_proposal._proposal_list[tx_hash] = create_tx_hash()
        self.assertTrue(self.network_proposal._check_registered_proposal(tx_hash))

    @patch_several(PATCHER_JSON_LOADS, PATCHER_JSON_DUMPS)
    def test_check_vote_result(self):
        # case(1): return False, when type is 'agree', len(prep) < 15, delegated >= 66%
        voter = self._generate_voter(14, 66, 0, 0, 100)
        proposal_info, _ = self._generate_proposal_info(NetworkProposalStatus.VOTING, voter)
        self.assertFalse(self.network_proposal._check_vote_result(NetworkProposalVote.AGREE, proposal_info))

        # case(2): return False, when type is 'agree', len(prep) >= 15, delegated < 66%
        voter = self._generate_voter(15, 65, 0, 0, 100)
        proposal_info, _ = self._generate_proposal_info(NetworkProposalStatus.VOTING, voter)
        self.assertFalse(self.network_proposal._check_vote_result(NetworkProposalVote.AGREE, proposal_info))

        # case(3): return True, when type is 'agree', len(prep) >= 15, delegated >= 66%
        voter = self._generate_voter(15, 66, 0, 0, 100)
        proposal_info, _ = self._generate_proposal_info(NetworkProposalStatus.VOTING, voter)
        self.assertTrue(self.network_proposal._check_vote_result(NetworkProposalVote.AGREE, proposal_info))

        # case(4): return False, when type is 'disagree', len(prep) < 7, delegated >= 33%
        voter = self._generate_voter(0, 0, 6, 33, 100)
        proposal_info, _ = self._generate_proposal_info(NetworkProposalStatus.VOTING, voter)
        self.assertFalse(self.network_proposal._check_vote_result(NetworkProposalVote.DISAGREE, proposal_info))

        # case(5): return False, when type is 'disagree', len(prep) >= 7, delegated < 33%
        voter = self._generate_voter(0, 0, 7, 32, 100)
        proposal_info, _ = self._generate_proposal_info(NetworkProposalStatus.VOTING, voter)
        self.assertFalse(self.network_proposal._check_vote_result(NetworkProposalVote.DISAGREE, proposal_info))

        # case(6): return True, when type is 'disagree', len(prep) >= 7, delegated >= 33%
        voter = self._generate_voter(0, 0, 7, 33, 100)
        proposal_info, _ = self._generate_proposal_info(NetworkProposalStatus.VOTING, voter)
        self.assertTrue(self.network_proposal._check_vote_result(NetworkProposalVote.DISAGREE, proposal_info))

    @patch_several(PATCHER_JSON_LOADS, PATCHER_JSON_DUMPS, PATCHER_CHECK_REGISTERED_PROPOSAL)
    def test_get_proposal(self):
        voter = self._generate_voter(2, 10, 3, 20, 100)
        proposal_info, self.network_proposal._proposal_list[proposal_info.id] = self._generate_proposal_info(
            NetworkProposalStatus.VOTING, voter)
        current_block_height = proposal_info.end_block_height + 1

        buf_proposal_info = deepcopy(proposal_info)
        for vote_type in ("agree", "disagree", "noVote"):
            buf_proposal_info.voter[vote_type]["amount"] = hex(buf_proposal_info.voter[vote_type]["amount"])

        expected_value = {
            "proposer": proposal_info.proposer,
            "id": proposal_info.id,
            "status": hex(proposal_info.status),
            "startBlockHeight": hex(proposal_info.start_block_height),
            "endBlockHeight": hex(proposal_info.end_block_height),
            "voter": buf_proposal_info.voter,
            "contents": {
                "description": proposal_info.description,
                "type": hex(proposal_info.type),
                "value": proposal_info.value
            }
        }

        self.network_proposal._check_registered_proposal.return_value = True
        # case(1): when finish prep period (end block height < current block height), NetworkProposalStatus == VOTING
        with patch.object(ProposalInfo, 'from_bytes', return_value=deepcopy(proposal_info)):
            result = self.network_proposal.get_proposal(proposal_info.id, current_block_height)
            expected_value["status"] = hex(NetworkProposalStatus.DISAPPROVED)
            self.assertEqual(result, expected_value)

        # case(2): when finish prep period (end block height < current block height), NetworkProposalStatus == APPROVED
        proposal_info.status = NetworkProposalStatus.APPROVED
        with patch.object(ProposalInfo, 'from_bytes', return_value=deepcopy(proposal_info)):
            result = self.network_proposal.get_proposal(proposal_info.id, current_block_height)
            expected_value["status"] = hex(NetworkProposalStatus.APPROVED)
            self.assertEqual(result, expected_value)

        # case(3): when finish prep period (end block height < current block height),
        # NetworkProposalStatus == DISAPPROVED
        proposal_info.status = NetworkProposalStatus.DISAPPROVED
        with patch.object(ProposalInfo, 'from_bytes', return_value=deepcopy(proposal_info)):
            result = self.network_proposal.get_proposal(proposal_info.id, current_block_height)
            expected_value["status"] = hex(NetworkProposalStatus.DISAPPROVED)
            self.assertEqual(result, expected_value)

        # case(4): when finish prep period (end block height < current block height), NetworkProposalStatus == CANCELED
        proposal_info.status = NetworkProposalStatus.CANCELED
        with patch.object(ProposalInfo, 'from_bytes', return_value=deepcopy(proposal_info)):
            result = self.network_proposal.get_proposal(proposal_info.id, current_block_height)
            expected_value["status"] = hex(NetworkProposalStatus.CANCELED)
            self.assertEqual(result, expected_value)

        current_block_height = proposal_info.end_block_height - 1
        proposal_info.status = NetworkProposalStatus.VOTING
        # case(5): during prep period (end block height >= current block height), Network proposal status == VOTING
        with patch.object(ProposalInfo, 'from_bytes', return_value=deepcopy(proposal_info)):
            result = self.network_proposal.get_proposal(proposal_info.id, current_block_height)
            expected_value["status"] = hex(NetworkProposalStatus.VOTING)
            self.assertEqual(result, expected_value)

        proposal_info.status = NetworkProposalStatus.APPROVED
        # case(6): during prep period (end block height >= current block height), Network proposal status == APPROVED
        with patch.object(ProposalInfo, 'from_bytes', return_value=deepcopy(proposal_info)):
            result = self.network_proposal.get_proposal(proposal_info.id, current_block_height)
            expected_value["status"] = hex(NetworkProposalStatus.APPROVED)
            self.assertEqual(result, expected_value)

        proposal_info.status = NetworkProposalStatus.DISAPPROVED
        # case(7): during prep period (end block height >= current block height), Network proposal status == DISAPPROVED
        with patch.object(ProposalInfo, 'from_bytes', return_value=deepcopy(proposal_info)):
            result = self.network_proposal.get_proposal(proposal_info.id, current_block_height)
            expected_value["status"] = hex(NetworkProposalStatus.DISAPPROVED)
            self.assertEqual(result, expected_value)

        proposal_info.status = NetworkProposalStatus.CANCELED
        # case(8): during prep period (end block height >= current block height), Network proposal status == CANCELED
        with patch.object(ProposalInfo, 'from_bytes', return_value=deepcopy(proposal_info)):
            result = self.network_proposal.get_proposal(proposal_info.id, current_block_height)
            expected_value["status"] = hex(NetworkProposalStatus.CANCELED)
            self.assertEqual(result, expected_value)

    @patch_several(PATCHER_JSON_LOADS, PATCHER_JSON_DUMPS)
    def test_get_proposal_list_during_prep_period(self):
        expected_proposal_list = {
            "proposals": []
        }
        voter = self._generate_voter(2, 10, 3, 20, 100)

        for i in range(5):
            proposal_info, self.network_proposal._proposal_list[proposal_info.id] = self._generate_proposal_info(
                NetworkProposalStatus.VOTING, voter)
            self.network_proposal._proposal_list_keys.append(proposal_info.id)
            proposal_info_in_dict = {
                "id": proposal_info.id,
                "description": proposal_info.description,
                "type": hex(proposal_info.type),
                "status": hex(proposal_info.status),
                "startBlockHeight": hex(proposal_info.start_block_height),
                "endBlockHeight": hex(proposal_info.end_block_height)
            }
            expected_proposal_list["proposals"].append(proposal_info_in_dict)

        current_block_height = proposal_info.end_block_height - 1
        result = self.network_proposal.get_proposal_list(current_block_height)
        self.assertEqual(expected_proposal_list, result)

    @patch_several(PATCHER_JSON_LOADS, PATCHER_JSON_DUMPS)
    def test_get_proposal_list_when_finish_prep_period(self):
        expected_proposal_list = {
            "proposals": []
        }
        voter = self._generate_voter(2, 10, 3, 20, 100)

        for i in range(5):
            proposal_info, self.network_proposal._proposal_list[proposal_info.id] = self._generate_proposal_info(
                NetworkProposalStatus.VOTING, voter)
            self.network_proposal._proposal_list_keys.append(proposal_info.id)
            proposal_info_in_dict = {
                "id": proposal_info.id,
                "description": proposal_info.description,
                "type": hex(proposal_info.type),
                # when end block height < current block height, NetworkProposalStatus should be DISAPPROVED
                "status": hex(NetworkProposalStatus.DISAPPROVED),
                "startBlockHeight": hex(proposal_info.start_block_height),
                "endBlockHeight": hex(proposal_info.end_block_height)
            }
            expected_proposal_list["proposals"].append(proposal_info_in_dict)

            current_block_height = proposal_info.end_block_height + 1
            result = self.network_proposal.get_proposal_list(current_block_height)
            self.assertEqual(expected_proposal_list, result)

    @patch_several(PATCHER_JSON_LOADS, PATCHER_JSON_DUMPS)
    def test_get_proposal_list_when_filter_by_type(self):
        for i in range(5):
            expected_proposal_list = {
                "proposals": []
            }
            voter = self._generate_voter(2, 10, 3, 20, 100)
            buf_network_proposal_type = [
                NetworkProposalType.TEXT, NetworkProposalType.REVISION, NetworkProposalType.MALICIOUS_SCORE,
                NetworkProposalType.PREP_DISQUALIFICATION, NetworkProposalType.STEP_PRICE
            ]
            proposal_info, self.network_proposal._proposal_list[proposal_info.id] = self._generate_proposal_info(
                NetworkProposalStatus.VOTING, voter, buf_network_proposal_type[i])
            self.network_proposal._proposal_list_keys.append(proposal_info.id)
            proposal_info_in_dict = {
                "id": proposal_info.id,
                "description": proposal_info.description,
                "type": hex(proposal_info.type),
                "status": hex(proposal_info.status),
                "startBlockHeight": hex(proposal_info.start_block_height),
                "endBlockHeight": hex(proposal_info.end_block_height)
            }
            expected_proposal_list["proposals"].append(proposal_info_in_dict)

            current_block_height = proposal_info.end_block_height - 1
            result = self.network_proposal.get_proposal_list(current_block_height, buf_network_proposal_type[i])
            self.assertEqual(i + 1, len(self.network_proposal._proposal_list))
            self.assertEqual(expected_proposal_list, result)

    @patch_several(PATCHER_JSON_LOADS, PATCHER_JSON_DUMPS)
    def test_get_proposal_list_when_filter_by_status(self):
        for i in range(4):
            expected_proposal_list = {
                "proposals": []
            }
            voter = self._generate_voter(2, 10, 3, 20, 100)
            buf_network_proposal_type = [
                NetworkProposalType.TEXT, NetworkProposalType.REVISION, NetworkProposalType.MALICIOUS_SCORE,
                NetworkProposalType.PREP_DISQUALIFICATION, NetworkProposalType.STEP_PRICE
            ]
            buf_network_proposal_status = [
                NetworkProposalStatus.VOTING, NetworkProposalStatus.APPROVED,
                NetworkProposalStatus.DISAPPROVED, NetworkProposalStatus.CANCELED
            ]
            proposal_info, self.network_proposal._proposal_list[proposal_info.id] = self._generate_proposal_info(
                buf_network_proposal_status[i], voter, buf_network_proposal_type[i])
            self.network_proposal._proposal_list_keys.append(proposal_info.id)
            proposal_info_in_dict = {
                "id": proposal_info.id,
                "description": proposal_info.description,
                "type": hex(proposal_info.type),
                "status": hex(proposal_info.status),
                "startBlockHeight": hex(proposal_info.start_block_height),
                "endBlockHeight": hex(proposal_info.end_block_height)
            }
            expected_proposal_list["proposals"].append(proposal_info_in_dict)

            current_block_height = proposal_info.end_block_height - 1
            result = self.network_proposal.get_proposal_list(current_block_height, None, buf_network_proposal_status[i])
            self.assertEqual(i + 1, len(self.network_proposal._proposal_list))
            self.assertEqual(expected_proposal_list, result)

    @patch_several(PATCHER_JSON_LOADS, PATCHER_JSON_DUMPS)
    def test_get_proposal_list_when_filter_by_both_type_and_status(self):
        expected_proposal_list = {
            "proposals": []
        }
        for i in range(5):
            voter = self._generate_voter(2, 10, 3, 20, 100)
            buf_network_proposal_type = [
                NetworkProposalType.TEXT, NetworkProposalType.REVISION, NetworkProposalType.REVISION,
                NetworkProposalType.PREP_DISQUALIFICATION, NetworkProposalType.STEP_PRICE
            ]
            proposal_info, self.network_proposal._proposal_list[proposal_info.id] = self._generate_proposal_info(
                NetworkProposalStatus.VOTING, voter, buf_network_proposal_type[i])
            self.network_proposal._proposal_list_keys.append(proposal_info.id)
            proposal_info_in_dict = {
                "id": proposal_info.id,
                "description": proposal_info.description,
                "type": hex(proposal_info.type),
                "status": hex(proposal_info.status),
                "startBlockHeight": hex(proposal_info.start_block_height),
                "endBlockHeight": hex(proposal_info.end_block_height)
            }
            if proposal_info.type == NetworkProposalType.REVISION:
                expected_proposal_list["proposals"].append(proposal_info_in_dict)

        current_block_height = proposal_info.end_block_height - 1
        result = self.network_proposal.get_proposal_list(current_block_height, NetworkProposalType.REVISION,
                                                         NetworkProposalStatus.VOTING)
        self.assertEqual(2, len(result['proposals']))
        self.assertEqual(5, len(self.network_proposal._proposal_list))
        self.assertEqual(expected_proposal_list, result)

    @patch_several(PATCHER_JSON_LOADS, PATCHER_JSON_DUMPS, PATCHER_VALIDATE_PROPOSAL, PATCHER_ARRAY_DB, PATCHER_DICT_DB)
    def test_register_proposal(self):

        class TmpArrayDB():
            def __init__(self):
                self.id = []

            def put(self, _id):
                self.id.append(_id)
                return self.id

            def __str__(self):
                return self.id

        attrs = {'return_value': TmpArrayDB()}
        self.network_proposal._proposal_list_keys = Mock()
        self.network_proposal._proposal_list_keys.configure_mock(**attrs)

        # check raise when not validate proposal
        voter = self._generate_voter(0, 0, 0, 0, 0)
        proposal_info, _ = self._generate_proposal_info(NetworkProposalStatus.VOTING, voter)
        with patch.object(self.network_proposal, '_validate_proposal', return_value=False):
            self.assertRaisesRegex(IconScoreException, "Invalid parameter", self.network_proposal.register_proposal,
                                   proposal_info.id, proposal_info.proposer, proposal_info.start_block_height,
                                   proposal_info.end_block_height,
                                   proposal_info.description, proposal_info.type, proposal_info.value, [])

        for i in range(5):
            voter = self._generate_voter(0, 0, 0, 0, DEFAULT_DELEGATED * COUNT_OF_MAIN_PREPS)
            proposal_info, _ = self._generate_proposal_info(NetworkProposalStatus.VOTING, voter)
            main_preps = [Prep(address, DEFAULT_DELEGATED) for address in voter["noVote"]["address"]]
            self.network_proposal.register_proposal(proposal_info.id, proposal_info.proposer,
                                                    proposal_info.start_block_height, proposal_info.end_block_height,
                                                    proposal_info.description,
                                                    proposal_info.type, proposal_info.value,
                                                    main_preps)
            self.assertEqual(i + 1, len(self.network_proposal._proposal_list))
            self.assertEqual(self.network_proposal._proposal_list[proposal_info.id], proposal_info.to_bytes())

    @patch_several(PATCHER_JSON_LOADS, PATCHER_JSON_DUMPS, PATCHER_CHECK_REGISTERED_PROPOSAL)
    def test_cancel_proposal(self):
        voter = self._generate_voter(1, DEFAULT_DELEGATED, 2, DEFAULT_DELEGATED, 100)
        proposal_info, self.network_proposal._proposal_list[proposal_info.id] = self._generate_proposal_info(
            NetworkProposalStatus.VOTING, voter)
        current_block_height = proposal_info.end_block_height - 1

        # case(1): raise revert when not check registered proposal
        with patch.object(ProposalInfo, 'from_bytes', return_value=proposal_info):
            self.assertRaisesRegex(IconScoreException, "No registered proposal", self.network_proposal.cancel_proposal,
                                   proposal_info.id, proposal_info.proposer, current_block_height)

        # case(2): raise revert when end block height < current block height
        current_block_height = proposal_info.end_block_height + 1
        self.network_proposal._check_registered_proposal.return_value = True
        with patch.object(ProposalInfo, 'from_bytes', return_value=proposal_info):
            self.assertRaisesRegex(IconScoreException, "This proposal has already expired",
                                   self.network_proposal.cancel_proposal,
                                   proposal_info.id, proposal_info.proposer, current_block_height)

        # case(3): raise revert when proposer is not the proposer who registered the proposal
        current_block_height = proposal_info.end_block_height - 1
        with patch.object(ProposalInfo, 'from_bytes', return_value=proposal_info):
            self.assertRaisesRegex(IconScoreException, "No permission - only for proposer",
                                   self.network_proposal.cancel_proposal,
                                   proposal_info.id, create_address(), current_block_height)

        # case(4): raise revert when status is not VOTING
        proposal_info.status = NetworkProposalStatus.APPROVED
        with patch.object(ProposalInfo, 'from_bytes', return_value=proposal_info):
            self.assertRaisesRegex(IconScoreException, "Can not be canceled - only voting proposal",
                                   self.network_proposal.cancel_proposal,
                                   proposal_info.id, proposal_info.proposer, current_block_height)

        # confirmed the correct proposal status is CANCELED
        proposal_info.status = NetworkProposalStatus.VOTING
        proposal_info.proposer = proposal_info.proposer
        with patch.object(ProposalInfo, 'from_bytes', return_value=proposal_info):
            id = proposal_info.id
            self.network_proposal.cancel_proposal(proposal_info.id, proposal_info.proposer, current_block_height)
            proposal_info.status = NetworkProposalStatus.CANCELED
            self.assertEqual(proposal_info, ProposalInfo.from_bytes(self.network_proposal._proposal_list[id]))

    @patch_several(PATCHER_JSON_LOADS, PATCHER_JSON_DUMPS, PATCHER_CHECK_VOTE_RESULT, PATCHER_CHECK_REGISTERED_PROPOSAL)
    def test_vote_proposal(self):
        voter = self._generate_voter(3, DEFAULT_DELEGATED, 2, DEFAULT_DELEGATED,
                                     DEFAULT_DELEGATED * COUNT_OF_MAIN_PREPS)
        voter_agree = voter["agree"]["address"][0]
        voter_disagree = voter["disagree"]["address"][0]
        proposal_info, self.network_proposal._proposal_list[proposal_info.id] = self._generate_proposal_info(
            NetworkProposalStatus.VOTING, voter)
        current_block_height = proposal_info.end_block_height - 1

        # case(1): raise revert when not check registered proposal
        with patch.object(ProposalInfo, 'from_bytes', return_value=proposal_info):
            self.assertRaisesRegex(IconScoreException, "No registered proposal", self.network_proposal.vote_proposal,
                                   proposal_info.id, proposal_info.proposer, NetworkProposalVote.AGREE,
                                   current_block_height, [])

        # case(2): raise revert when end block height < current block height
        current_block_height = proposal_info.end_block_height + 1
        self.network_proposal._check_registered_proposal.return_value = True
        with patch.object(ProposalInfo, 'from_bytes', return_value=proposal_info):
            self.assertRaisesRegex(IconScoreException, "This proposal has already expired",
                                   self.network_proposal.vote_proposal, proposal_info.id, proposal_info.proposer,
                                   NetworkProposalVote.AGREE,
                                   current_block_height, [])

        # case(3): raise revert status is CANCELED
        current_block_height = proposal_info.end_block_height - 1
        proposal_info.status = NetworkProposalStatus.CANCELED
        with patch.object(ProposalInfo, 'from_bytes', return_value=proposal_info):
            self.assertRaisesRegex(IconScoreException, "This proposal has already canceled",
                                   self.network_proposal.vote_proposal, proposal_info.id, proposal_info.proposer,
                                   NetworkProposalVote.AGREE,
                                   current_block_height, [])

        # case(4): raise revert voter has already voted for agree
        with patch.object(ProposalInfo, 'from_bytes', return_value=proposal_info):
            proposal_info.status = NetworkProposalStatus.APPROVED
            self.assertRaisesRegex(IconScoreException, "Already voted",
                                   self.network_proposal.vote_proposal, proposal_info.id, voter_agree,
                                   NetworkProposalVote.AGREE,
                                   current_block_height, [])
            proposal_info.status = NetworkProposalStatus.DISAPPROVED
            self.assertRaisesRegex(IconScoreException, "Already voted",
                                   self.network_proposal.vote_proposal, proposal_info.id, voter_agree,
                                   NetworkProposalVote.AGREE,
                                   current_block_height, [])
            proposal_info.status = NetworkProposalStatus.VOTING
            self.assertRaisesRegex(IconScoreException, "Already voted",
                                   self.network_proposal.vote_proposal, proposal_info.id, voter_agree,
                                   NetworkProposalVote.AGREE,
                                   current_block_height, [])

        # case(5): raise revert voter has already voted for disagree
        with patch.object(ProposalInfo, 'from_bytes', return_value=proposal_info):
            proposal_info.status = NetworkProposalStatus.APPROVED
            self.assertRaisesRegex(IconScoreException, "Already voted",
                                   self.network_proposal.vote_proposal, proposal_info.id, voter_disagree,
                                   NetworkProposalVote.DISAGREE,
                                   current_block_height, [])
            proposal_info.status = NetworkProposalStatus.DISAPPROVED
            self.assertRaisesRegex(IconScoreException, "Already voted",
                                   self.network_proposal.vote_proposal, proposal_info.id, voter_disagree,
                                   NetworkProposalVote.DISAGREE,
                                   current_block_height, [])
            proposal_info.status = NetworkProposalStatus.VOTING
            self.assertRaisesRegex(IconScoreException, "Already voted",
                                   self.network_proposal.vote_proposal, proposal_info.id, voter_disagree,
                                   NetworkProposalVote.DISAGREE,
                                   current_block_height, [])

        # case(6): when status is VOTING and check vote result is True and vote type is AGREE,
        # check status is APPROVED and return values is correct
        buf_proposal_info = deepcopy(proposal_info)
        with patch.object(ProposalInfo, 'from_bytes', return_value=deepcopy(buf_proposal_info)):
            self.assertEqual(buf_proposal_info.status, NetworkProposalStatus.VOTING)
            self.network_proposal._proposal_list[proposal_info.id] = create_tx_hash()
            buf_voter_address = voter["noVote"]["address"][0]
            main_preps = [Prep(address, DEFAULT_DELEGATED if address != buf_voter_address else DEFAULT_DELEGATED * 2)
                          for address in
                          voter["agree"]["address"] + voter["disagree"]["address"] + voter["noVote"]["address"]]
            approved, proposal_info_type, proposal_info_value = self.network_proposal.vote_proposal(proposal_info.id,
                                                                                                    buf_voter_address,
                                                                                                    NetworkProposalVote.AGREE,
                                                                                                    current_block_height,
                                                                                                    main_preps)
            buf_proposal_info.status = NetworkProposalStatus.APPROVED
            buf_proposal_info.voter["agree"]["address"].append(str(buf_voter_address))
            buf_proposal_info.voter["agree"]["amount"] += DEFAULT_DELEGATED * 2
            buf_proposal_info.voter["noVote"]["address"].remove(str(buf_voter_address))
            buf_proposal_info.voter["noVote"]["amount"] -= DEFAULT_DELEGATED * 2
            self.assertEqual(self.network_proposal._proposal_list[proposal_info.id], buf_proposal_info.to_bytes())
            self.assertTrue(approved)
            self.assertEqual(proposal_info.type, proposal_info_type)
            self.assertEqual(proposal_info.value, proposal_info_value)

        # case(7): when status is VOTING and check vote result is True and vote type is DISAGREE,
        # check status is DISAPPROVED and return values is correct
        buf_proposal_info = deepcopy(proposal_info)
        with patch.object(ProposalInfo, 'from_bytes', return_value=deepcopy(buf_proposal_info)):
            buf_proposal_info.status = NetworkProposalStatus.VOTING
            self.assertEqual(buf_proposal_info.status, NetworkProposalStatus.VOTING)
            buf_voter_address = voter["noVote"]["address"][0]
            main_preps = [Prep(address, DEFAULT_DELEGATED if address != buf_voter_address else DEFAULT_DELEGATED * 2)
                          for address in
                          voter["agree"]["address"] + voter["disagree"]["address"] + voter["noVote"]["address"]]
            approved, proposal_info_type, proposal_info_value = self.network_proposal.vote_proposal(proposal_info.id,
                                                                                                    buf_voter_address,
                                                                                                    NetworkProposalVote.DISAGREE,
                                                                                                    current_block_height,
                                                                                                    main_preps)
            buf_proposal_info.status = NetworkProposalStatus.DISAPPROVED
            buf_proposal_info.voter["disagree"]["address"].append(str(buf_voter_address))
            buf_proposal_info.voter["disagree"]["amount"] += DEFAULT_DELEGATED * 2
            buf_proposal_info.voter["noVote"]["address"].remove(str(buf_voter_address))
            buf_proposal_info.voter["noVote"]["amount"] -= DEFAULT_DELEGATED * 2
            self.assertEqual(self.network_proposal._proposal_list[proposal_info.id], buf_proposal_info.to_bytes())
            self.assertFalse(approved)
            self.assertEqual(proposal_info.type, proposal_info_type)
            self.assertEqual(proposal_info.value, proposal_info_value)

    @staticmethod
    def _generate_voter(cnt_agree_voter: int, delegated_agree_voter: int, cnt_disagree_voter: int,
                        delegated_disagree_voter: int, total_delegated: int):
        voter = {
            "agree": {
                "address": [str(create_address()) for _ in range(cnt_agree_voter)],
                "amount": delegated_agree_voter
            },
            "disagree": {
                "address": [str(create_address()) for _ in range(cnt_disagree_voter)],
                "amount": delegated_disagree_voter
            },
            "noVote": {
                "address": [
                    str(create_address()) for _ in range(COUNT_OF_MAIN_PREPS - cnt_agree_voter - cnt_disagree_voter)],
                "amount": total_delegated - delegated_agree_voter - delegated_disagree_voter
            }
        }
        return voter

    @staticmethod
    def _generate_proposal_info(status: int, voter: dict, type: int = NetworkProposalType.MALICIOUS_SCORE) -> (
            ProposalInfo, bytes):
        id = create_tx_hash()
        proposer = create_address()
        description = "Disqualify P-Rep A; P-Rep A does not maintain node"
        value = {
            "address": bytes.hex(Address.to_bytes(create_address()))
        }
        start_block_height = 1
        end_block_height = 10
        proposal_info = ProposalInfo(id, proposer, description, type, value, start_block_height,
                                     end_block_height, status, voter)
        buf_proposal_info = deepcopy(proposal_info)
        return proposal_info, buf_proposal_info.to_bytes()