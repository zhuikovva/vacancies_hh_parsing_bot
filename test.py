from environs import Env

env = Env()
env.read_env()

token = "998624144:AAEOX-3LkHdSManAHVUXs5f-W_eVtzVxEfo"
print("Токен:", repr(token))