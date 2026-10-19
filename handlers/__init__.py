"""Register every handler module with the application.

Watcher groups (lower runs first):
  group 1 = PM router, proof inbox, weekly counter
  group 2 = FAQ watcher, keyword watcher
"""

from . import (
    announce,
    countdown,
    faq,
    feedback,
    keywords,
    poll,
    proof,
    quiz,
    remind,
    reply,
    schedule,
    start,
    top,
)


def register_all(app):
    for module in (start, announce, faq, poll, schedule, keywords, proof,
                   countdown, feedback, quiz, top, remind, reply):
        module.register(app)
