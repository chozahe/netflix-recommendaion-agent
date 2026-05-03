from app.conversation.classifier import classify_turn



def test_classifier_detects_feedback_rejection():
    turn_type = classify_turn(
        message="это отстой, слишком старое",
        state="recommended",
    )
    assert turn_type == "feedback_rejection"
