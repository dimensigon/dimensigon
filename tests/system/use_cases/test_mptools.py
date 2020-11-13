import logging
import random
import time

from dimensigon.use_cases import mptools as mpt
from dimensigon.use_cases import mptools_events as events

FORMAT = '%(asctime)-15s [%(process)d] %(processName)-20s %(name)-25s %(message)s'
logging.basicConfig(format=FORMAT, level=logging.DEBUG)


class FoodDelivery(mpt.TimerWorker):
    INTERVAL_SECS = 1
    dishes = ['Fish&Chips', 'Pasta', 'PaAmbTomaquet']

    def main_func(self, *args, **kwargs):
        dish = random.choice(self.dishes)
        calories = int(random.random() * 80)
        self.logger.debug(f"Delivering {dish} with {calories} calories")
        self.publish_q.safe_put(events.EventMessage(dish, "FoodDelivery",
                                                    calories=calories))


class Diner(mpt.Worker):

    def callback(self, event: events.EventMessage):
        self.logger.info(f"Eating {event.event_type} with {event.kwargs['calories']} calories")

    def startup(self):
        self.dispatcher.listen('PaAmbTomaquet', self.callback)
        super().startup()

    def main_func(self, *args, **kwargs):
        time.sleep(0.02)


def main(die_in_secs):
    with mpt.MainContext() as main_ctx:
        if die_in_secs:
            die_time = time.time() + die_in_secs
            main_ctx.logger.debug(f"Application die time is in {die_in_secs} seconds")
        else:
            die_time = None

        # mpt.init_signals(main_ctx.shutdown_event, mpt.default_signal_handler, mpt.default_signal_handler)

        main_ctx.Proc(FoodDelivery)
        main_ctx.Proc(Diner)


        while not main_ctx.shutdown_event.is_set():
            if die_time and time.time() > die_time:
                raise RuntimeError("Application has run too long.")
            main_ctx.forward_events()

        main_ctx.logger.debug("Exiting main context")


if __name__ == '__main__':
    logger = logging.getLogger('dm')
    logger.info("Starting process")
    main(10)
