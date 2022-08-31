from viadot.config import local_config
from viadot.sources import Outlook


def test_outlook_to_df():
    outlook_env_vars = local_config.get("OUTLOOK")
    outlook = Outlook(
        mailbox_name=outlook_env_vars["mail_example"],
        start_date="2022-04-28",
        end_date="2022-04-29",
    )
    df = outlook.to_df()
    assert df.shape[1] == 10
    assert df.empty == False
