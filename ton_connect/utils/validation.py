import typing as t

from ton_core import NetworkGlobalID

from ..exceptions import (
    WalletMissingRequiredFeaturesError,
    WalletNotSupportFeatureError,
    WalletWrongNetworkError,
)
from ..models.app import AppWallet
from ..models.feature import (
    SendTransactionFeature,
    SignDataFeature,
    SignMessageFeature,
)
from ..models.wallet import Wallet

_F = t.TypeVar("_F")


def _find_feature(features: t.Sequence[t.Any], feature_type: type[_F]) -> _F | None:
    """Return the first *feature_type* entry in *features*, or ``None``."""
    for feature in features:
        if isinstance(feature, feature_type):
            return feature
    return None


def _verify_message_limits(
    feature: SendTransactionFeature | SignMessageFeature,
    subject: str,
    num_messages: int,
    has_extra_currency: bool,
) -> None:
    """Check the message count and extra-currency limits of *feature*; *subject* names the declaring side."""
    if num_messages > 0 and feature.max_messages is not None and num_messages > feature.max_messages:
        raise WalletNotSupportFeatureError(
            f"{subject} supports max {feature.max_messages} messages, but {num_messages} were requested"
        )

    if has_extra_currency and not feature.extra_currency_supported:
        raise WalletNotSupportFeatureError(f"{subject} does not support extra currencies")


def verify_wallet_features(wallet: Wallet) -> None:
    """Verify that the wallet declares required features.

    :param wallet: Connected wallet to validate.
    :raises WalletMissingRequiredFeaturesError: If ``SendTransaction`` is not declared.
    """
    if not wallet.device.features:
        raise WalletMissingRequiredFeaturesError("Wallet did not declare any features")

    has_send_transaction = any(isinstance(f, SendTransactionFeature) for f in wallet.device.features)
    if not has_send_transaction:
        raise WalletMissingRequiredFeaturesError("Wallet does not declare SendTransaction support")


def verify_send_transaction_support(
    wallet: Wallet,
    num_messages: int = 0,
    app_wallet: AppWallet | None = None,
    *,
    has_extra_currency: bool = False,
) -> SendTransactionFeature:
    """Verify ``SendTransaction`` support on both app and wallet layers.

    :param wallet: Connected wallet with device capabilities.
    :param num_messages: Number of outgoing messages (0 to skip check).
    :param app_wallet: Wallet application descriptor, or ``None``.
    :param has_extra_currency: Whether extra-currency transfers are included.
    :return: ``SendTransactionFeature`` from the connected wallet.
    :raises WalletNotSupportFeatureError: If any validation step fails.
    """
    if app_wallet is not None:
        app_feature = _find_feature(app_wallet.features, SendTransactionFeature)
        if app_feature is None:
            raise WalletNotSupportFeatureError(
                f"Wallet app `{app_wallet.app_name}` does not declare SendTransaction support"
            )
        _verify_message_limits(app_feature, f"Wallet app `{app_wallet.app_name}`", num_messages, has_extra_currency)

    wallet_feature = _find_feature(wallet.device.features, SendTransactionFeature)
    if wallet_feature is None:
        raise WalletNotSupportFeatureError("Wallet does not support SendTransaction")
    _verify_message_limits(wallet_feature, "Wallet", num_messages, has_extra_currency)

    return wallet_feature


def verify_sign_message_support(
    wallet: Wallet,
    num_messages: int = 0,
    *,
    has_extra_currency: bool = False,
) -> SignMessageFeature:
    """Verify ``SignMessage`` support of the connected wallet.

    Only the features declared on connect are checked, as in the JS SDK: the wallets list does not carry ``SignMessage``.

    :param wallet: Connected wallet with device capabilities.
    :param num_messages: Number of outgoing messages (0 to skip check).
    :param has_extra_currency: Whether extra-currency transfers are included.
    :return: ``SignMessageFeature`` from the connected wallet.
    :raises WalletNotSupportFeatureError: If any validation step fails.
    """
    wallet_feature = _find_feature(wallet.device.features, SignMessageFeature)
    if wallet_feature is None:
        raise WalletNotSupportFeatureError("Wallet does not support SignMessage")
    _verify_message_limits(wallet_feature, "Wallet", num_messages, has_extra_currency)

    return wallet_feature


def verify_sign_data_support(
    wallet: Wallet,
    payload_type: str | None = None,
    app_wallet: AppWallet | None = None,
) -> SignDataFeature:
    """Verify ``SignData`` support on both app and wallet layers.

    :param wallet: Connected wallet with device capabilities.
    :param payload_type: Payload type to validate (e.g. ``"text"``), or ``None``.
    :param app_wallet: Wallet application descriptor, or ``None``.
    :return: ``SignDataFeature`` from the connected wallet.
    :raises WalletNotSupportFeatureError: If any validation step fails.
    """
    if app_wallet is not None:
        app_feature = _find_feature(app_wallet.features, SignDataFeature)
        if app_feature is None:
            raise WalletNotSupportFeatureError(f"Wallet app `{app_wallet.app_name}` does not declare SignData support")

        if payload_type is not None and payload_type not in app_feature.types:
            raise WalletNotSupportFeatureError(
                f"Wallet app `{app_wallet.app_name}` does not support "
                f"SignData type `{payload_type}`, supported: {app_feature.types}"
            )

    wallet_feature = _find_feature(wallet.device.features, SignDataFeature)
    if wallet_feature is None:
        raise WalletNotSupportFeatureError("Wallet does not support SignData")

    if payload_type is not None and payload_type not in wallet_feature.types:
        raise WalletNotSupportFeatureError(
            f"Wallet does not support SignData type `{payload_type}`, supported: {wallet_feature.types}"
        )

    return wallet_feature


def verify_wallet_network(
    wallet: Wallet,
    expected_network: NetworkGlobalID,
) -> None:
    """Verify the wallet operates on the expected network.

    :param wallet: Connected wallet.
    :param expected_network: Expected network identifier.
    :raises WalletWrongNetworkError: If the network does not match.
    """
    if wallet.account.network != expected_network:
        raise WalletWrongNetworkError(f"Expected network {expected_network.value}, got {wallet.account.network.value}")
