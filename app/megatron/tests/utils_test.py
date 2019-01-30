import pytest
from megatron import utils

pytestmark = pytest.mark.django_db

class TestRemoveSensitiveData(object):
    @pytest.mark.parametrize("msg, expected", [
        (
            {'text': 'I am a card 1111-1111-1111-1111'},
            {'text': 'I am a card ****-****-****-****'},
        ),
        (
            {'text': 'I am also card 1111 1111 1111 1111'},
            {'text': 'I am also card **** **** **** ****'}
        ),
        (
            {'text': 'nother card 1111111111111111'},
            {'text': 'nother card ****************'},
        ),
        (
            {
                'text': 'Nothin',
                'attachments': [
                    {
                        'fields': [
                            {
                                'title': 'Card Number',
                                'value': '1234-1234-2343-3433'
                            },
                            {
                                'title': 'Not a card number',
                                'value': 'Still not a num'
                            }
                        ]
                    }
                ]
            },
            {
                'text': 'Nothin',
                'attachments': [
                    {
                        'fields': [
                            {
                                'title': 'Card Number',
                                'value': '**** **** **** ****'
                            },
                            {
                                'title': 'Not a card number',
                                'value': 'Still not a num'
                            }
                        ]
                    }
                ]
            }
        ),
        (
            {'text': [['unexpected'], 'not', 'string']},
            {'text': '**** Unexpected ****'}
        ),
    ])
    def test_sensitive_data_removed(self, msg, expected):
        cleaned_msg = utils.remove_sensitive_data(msg)
        assert cleaned_msg == expected
