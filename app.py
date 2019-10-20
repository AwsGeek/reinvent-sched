#!/usr/bin/env python3

from aws_cdk import core

from reInventSched.reInventSched_stack import reInventSchedStack


app = core.App()
reInventSchedStack(app, "reInventSched")

app.synth()
