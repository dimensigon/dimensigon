import os

import click

from dm.web import create_app, db, repo, interactor, catalog_manager as cm

app = create_app(os.getenv('FLASK_CONFIG') or 'dev')


@app.shell_context_processor
def make_shell_context():
    return dict(db=db, repo=repo, cm=cm, interactor=interactor)


@app.cli.command(help='executes the specified tests')
@click.argument('test_names', nargs=-1)
def test(test_names):
    import unittest
    if test_names:
        tests = unittest.TestLoader().loadTestsFromNames(test_names)
    else:
        tests = unittest.TestLoader().discover('tests')
    unittest.TextTestRunner(verbosity=2).run(tests)