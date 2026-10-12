from providers.telephony.livekit_sip import LiveKitSipRoutingAdapter


def test_extracts_trunk_phone_number_for_routing() -> None:
    adapter = LiveKitSipRoutingAdapter()
    ctx = adapter.extract_inbound_context(
        room_name="call-abc",
        job_metadata='{"business_id":"demo_salon"}',
        participant_attributes={
            "sip.phoneNumber": "+15551112222",
            "sip.trunkPhoneNumber": "+15550100",
        },
    )
    assert ctx.called_number == "+15550100"
    assert ctx.caller_number == "+15551112222"
    assert ctx.dispatch_metadata["business_id"] == "demo_salon"


def test_does_not_use_caller_provided_business_id_without_metadata() -> None:
    adapter = LiveKitSipRoutingAdapter()
    ctx = adapter.extract_inbound_context(
        room_name="call-abc",
        job_metadata="",
        participant_attributes={"sip.trunkPhoneNumber": "+15550100"},
    )
    assert "business_id" not in ctx.dispatch_metadata
