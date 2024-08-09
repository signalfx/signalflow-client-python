from signalfx.signalflow.messages import (
    ChannelAbortMessage,
    DataMessage,
    EndOfChannelMessage,
    ErrorMessage,
    EventMessage,
    ExpiredTsIdMessage,
    InfoMessage,
    JobProgressMessage,
    JobStartMessage,
    MetadataMessage,
    StreamStartMessage,
)


def test_stringification():
    attrs = {"a": 42}
    assert str(StreamStartMessage(1234)) == "stream_start@1234"
    assert str(JobStartMessage(1234, "myhandle")) == "job_start@1234: myhandle"
    assert (
        str(JobProgressMessage(1234, "myprogress")) == "job_progress@1234: myprogress"
    )
    assert (
        str(ChannelAbortMessage(1234, "myabortinfo"))
        == "channel_abort@1234: myabortinfo"
    )
    assert str(EndOfChannelMessage(1234)) == "end_of_channel@1234"
    assert str(InfoMessage(1234, "mymessage")) == "info@1234: mymessage"
    assert (
        str(EventMessage("tsid1234", 1234, "mymetadata", attrs))
        == "event@1234: mymetadata: a: 42"
    )
    assert str(MetadataMessage("tsid1234", attrs)).startswith("metadata for tsid1234")
    assert str(ExpiredTsIdMessage("tsid1234")) == "expired_tsid for tsid1234"
    assert (
        str(DataMessage(1234, [{"tsId": "tsid1234", "value": "myvalue"}]))
        == "data@1234: tsid1234: myvalue"
    )
    assert str(ErrorMessage("myerrors")) == "error: myerrors"
