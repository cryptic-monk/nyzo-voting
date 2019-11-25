import sys
import urllib.request
import hashlib
import binascii
import subprocess

# Where the sig files reside (if retrieved from remote).
SIG_FILE_LOCATION = "https://raw.githubusercontent.com/cryptic-monk/nyzo-voting/master/sig/"
# Where the managed verifier file resides.
MANAGED_VERIFIERS_LOCATION = "/var/lib/nyzo/production/managed_verifiers"
# Jar location: where the main Nyzo jar lies. Change this if your installation user is not 'ubuntu'.
JAR_LOCATION = "/home/ubuntu/nyzoVerifier/build/libs/nyzoVerifier-1.0.jar"
# Where the no/abstention vote transactions (1 micronyzo) go to, recipient gets nothing.
VOTE_RECIPIENT = "id__8bo.fFTWDC1m2hX6UWxw6Vgs2IsWTCJyIFAcm3V.BytZgoahsDN5"

# Those are needed to convert the (old) nyzo hex format of priv keys to the new "nyzo string" format accepted by the CLI
# as per:
# https://github.com/n-y-z-o/nyzoVerifier/blob/master/src/main/java/co/nyzo/verifier/nyzoString/NyzoStringEncoder.java
# and: https://github.com/EggPool/Vanozy/blob/master/vanozy/nyzostrings/nyzostringencoder.py
CHARACTER_LOOKUP = (
    "0123456789abcdefghijkmnopqrstuvwxyzABCDEFGHIJKLMNPQRSTUVWXYZ-.~_"
)
VALUE_LOOKUP = {}
for position, char in enumerate(CHARACTER_LOOKUP):
    VALUE_LOOKUP[CHARACTER_LOOKUP[position]] = position

# the signatures we're voting on
sigs = []
# our managed verifiers (private keys)
verifiers = []


# Get signatures for the given NCFP from remote repo.
def get_sigs_remote(ncfp):
    url = SIG_FILE_LOCATION + ncfp + ".sig"
    print("Retrieving signatures from: %s." % url)
    try:
        response = urllib.request.urlopen(url)
        data = response.read()
        text = data.decode("utf-8")
        lines = text.split("\n")
        for line in lines:
            if len(line.strip()) != 0 and line.startswith("sig_"):
                sigs.append(line.strip())
        if len(sigs) > 0:
            print("Found %d signature(s) to vote on." % len(sigs))
            return True
    except Exception as ex:
        print("ERROR: %s." % str(ex))
        return False
    return False


# Get signatures from local vote.sig file.
def get_sigs_local():
    print("Retrieving signatures from vote.sig.")
    try:
        with open("vote.sig") as fp:
            line = fp.readline()
            while line:
                if len(line.strip()) != 0 and line.startswith("sig_"):
                    sigs.append(line.strip())
                line = fp.readline()
            if len(sigs) > 0:
                print("Found %d signature(s) to vote on." % len(sigs))
                return True
    except Exception as ex:
        print("ERROR: %s." % str(ex))
        return False
    return False


# Load managed verifiers from their original file.
def load_managed_verifiers():
    print("Loading managed verifiers.")
    try:
        with open(MANAGED_VERIFIERS_LOCATION) as fp:
            line = fp.readline()
            while line:
                if line.find("#") >= 0:
                    line = line[:line.find("#")]
                    line = line.strip()
                if len(line) != 0:
                    items = line.split(":")
                    if len(items) == 3:
                        verifiers.append(nyzo_privkey_hex_to_string(items[2]))
                line = fp.readline()
            if len(verifiers) > 0:
                print("Found %d verifier(s)." % len(verifiers))
                return True
    except Exception as ex:
        print("ERROR: %s." % str(ex))
        return False
    return False


# Decode a Nyzo string into a bytearray.
def decode_nyzo_string(encoded_string):
    array_length = (len(encoded_string) * 6 + 7) // 8
    array = bytearray(array_length)
    for i in range(array_length):
        left_character = encoded_string[i * 8 // 6]
        right_character = encoded_string[i * 8 // 6 + 1]
        left_value = VALUE_LOOKUP.get(left_character, 0)
        right_value = VALUE_LOOKUP.get(right_character, 0)
        bit_offset = (i * 2) % 6
        array[i] = (((left_value << 6) + right_value) >> 4 - bit_offset) & 0xFF
    return array


# Encode a bytearray into a Nyzo string.
def encode_nyzo_string(byte_array):
    index = 0
    bit_offset = 0
    encoded_string = ""
    while index < len(byte_array):
        left_byte = byte_array[index] & 0xFF
        right_byte = byte_array[index + 1] & 0xFF if index < len(byte_array) - 1 else 0
        lookup_index = (((left_byte << 8) + right_byte) >> (10 - bit_offset)) & 0x3F
        encoded_string += CHARACTER_LOOKUP[lookup_index]
        if bit_offset == 0:
            bit_offset = 6
        else:
            index += 1
            bit_offset -= 2
    return encoded_string


# Convert a Nyzo 'dashed' hex private key into a Nyzo string private key.
def nyzo_privkey_hex_to_string(nyzo_hex):
    prefix = decode_nyzo_string("key_")
    hex_clean = ""
    for letter in nyzo_hex.lower():
        # remove any noise, a bit like the Java version does it
        if letter in ["0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "a", "b", "c", "d", "e", "f"]:
            hex_clean += letter
    content = bytearray.fromhex(hex_clean)
    checksum_length = 4 + (3 - (len(content) + 2) % 3) % 3
    full_buffer = prefix + len(content).to_bytes(1, "little") + content
    full_buffer += hashlib.sha256(hashlib.sha256(full_buffer).digest()).digest()[:checksum_length]
    return encode_nyzo_string(full_buffer)


# Poor man's 'expect', waits for the given string to appear in stdout of an external process, only works
# if there's a newline at the end of said output.
def poorman_expect(stdout, expect):
    found = False
    while not found:
        line = stdout.readline().decode()
        print(line.rstrip())
        if expect in line:
            found = True


# Sends a voting transaction ('no', or 'abstention'), regarding the given signature.
# The vote is stored in the transaction data. First, the signature in question is hashed into
# an MD5 checksum, then it's base 64 encoded (the newline char is removed), the result should now
# be 24 characters long. Finally, " n" or " a" are added for 'no' or 'abstention'.
# MD5 should be plenty enough for our purpose, as we're not in a range where a (very theoretical)
# collision would matter.
# The chainalytics tool will have to pull the relevant sigs from the chain, look for voting data and verify
# whether the verifier that sent the transaction is still in cycle at the moment.
def send_vote_transaction(vote, sig):
    data_string = binascii.b2a_base64(hashlib.md5(sig.encode()).digest()).strip().decode()
    if vote == "no":
        data_string += " n\n"
    else:
        data_string += " a\n"
    print("Starting Nyzo CLI.")
    process = subprocess.Popen(["java", "-jar", JAR_LOCATION, "co.nyzo.verifier.client.Client"],
                               stdin=subprocess.PIPE,
                               stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE,
                               bufsize=1)
    poorman_expect(process.stdout, "exit Nyzo client")
    count = 1
    for verifier in verifiers:
        print("Sending vote transaction for verifier %d." % count)
        process.stdin.write(b"ST\n")  # send transaction
        process.stdin.write(verifier.encode() + b"\n")  # sender private key
        process.stdin.write(VOTE_RECIPIENT.encode() + b"\n")  # recipient public ID
        process.stdin.write(data_string.encode())
        process.stdin.write(b"0.000001\n")  # one micronyzo
        process.stdin.write(b"y\n")  # yes, do it
        process.stdin.flush()
        poorman_expect(process.stdout, "frozen edge:")
        count += 1
    process.stdin.write(b"X\n")  # exit
    process.stdin.flush()
    poorman_expect(process.stdout, "fin.")
    return


# Signs the cycle transaction with the given signature.
def sign_cycle_transaction(sig):
    print("Signing cycle transaction for %s." % sig)
    process = subprocess.Popen(["java", "-jar", JAR_LOCATION, "co.nyzo.verifier.scripts.CycleTransactionSignScript", sig],
                               stdin=subprocess.PIPE,
                               stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE,
                               bufsize=1)
    poorman_expect(process.stdout, "fin.")


# Execute the given vote (yes, no, abstention) using the given source for the signatures.
def do_vote(vote, source):
    # first, get the signature(s)
    if source.upper().startswith("NCFP"):
        success = get_sigs_remote(source.upper())
        if not success:
            print("Could not retrieve voting signature file for: %s." % source.upper())
            exit(1)
    elif source.lower() == "vote.sig":
        success = get_sigs_local()
        if not success:
            print("Could not load votes from local file (vote.sig).")
            exit(1)
    elif source.startswith("sig_"):
        sigs.append(source.strip())
        print("One signature to vote on.")
    # now, let's vote
    # load managed verifier private keys if needed
    if vote in ["no", "abstention"]:
        load_managed_verifiers()
    for sig in sigs:
        print("Voting %s on signature %s." % (vote, sig))
        if vote == "yes":
            sign_cycle_transaction(sig)
        elif vote in ["no", "abstention"]:
            send_vote_transaction(vote, sig)


# Print simple usage instructions and exit with a wrong parameters exit code.
def print_usage_and_exit():
    print("Usage:")
    print("    sudo python3 vote.py yes NCFP3")
    print("    sudo python3 vote.py no NCFP3")
    print("    sudo python3 vote.py abstention NCFP3\n")
    print("Please see readme for further details and alternative voting modes.")
    exit(64)


# Startup: command line sanity check, then start voting.
if __name__ == "__main__":
    print("Nyzo Voting Script.\n")
    # command line sanity check: needs 2 parameters
    if len(sys.argv) != 3:
        print_usage_and_exit()
    # command line sanity check: only 3 types of votes can be cast
    if sys.argv[1].lower() not in ["yes", "no", "abstention"]:
        print_usage_and_exit()
    # command line sanity check: 3 types of voting, via NCFP name, via vote.sig file, or a direct vote on a signature
    if not sys.argv[2].upper().startswith("NCFP") and not sys.argv[2].lower() == "vote.sig" and not sys.argv[2].startswith("sig_"):
        print_usage_and_exit()
    do_vote(sys.argv[1].lower(), sys.argv[2])
