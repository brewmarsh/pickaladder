import datetime
from unittest.mock import MagicMock, patch
from mockfirestore import MockFirestore
from pickaladder.match.services import MatchService
import firebase_admin
from firebase_admin import firestore

# Setup mock firestore
db = MockFirestore()

# Patch transactional
with patch('firebase_admin.firestore.transactional', side_effect=lambda x: x):
    # Setup users
    db.collection('users').document('user1').set({'name': 'User 1'})
    db.collection('users').document('user2').set({'name': 'User 2'})

    form_data = {
        'player1': 'user1',
        'player2': 'user2',
        'player1_score': 11,
        'player2_score': 9,
        'match_date': datetime.date.today(),
        'match_type': 'singles'
    }
    current_user = {'uid': 'user1'}

    # Patch DocumentReference.get to handle transaction
    orig_get = firestore.DocumentReference.get
    def patched_get(self, transaction=None):
        return orig_get(self)

    with patch('google.cloud.firestore_v1.document.DocumentReference.get', patched_get):
        with patch('pickaladder.match.services.MatchService.get_candidate_player_ids', return_value={'user1', 'user2'}):
            try:
                # We need to mock db.transaction() too
                mock_transaction = MagicMock()
                # Mock transaction.get to use p1_ref.get
                mock_transaction.get.side_effect = lambda ref: ref.get()

                with patch.object(db, 'transaction', return_value=mock_transaction):
                    res = MatchService.process_match_submission(db, form_data, current_user)
                    print(f"Success: {res}")
            except Exception as e:
                print(f"Error: {e}")
                import traceback
                traceback.print_exc()
