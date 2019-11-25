# Nyzo Voting
A Python script to facilitate voting on Nyzo NCFPs (Community Fund Proposals).

## How To
Install the script with:  

`wget ...`

The script has no dependencies apart from the Python Standard Libraries and python3 
should come preinstalled on most Unix systems. 

This scripts targets the SENTINEL, which should have the private keys of all your in-cycle
verifiers. It requires Nyzo version 552 or higher for the accelerated voting process.

Vote as follows: 
 
`sudo python3 vote.py yes NCFP3`  
`sudo python3 vote.py no NCFP3`  
`sudo python3 vote.py abstention NCFP3`

## How To (For the Paranoid)

- Instead of wgetting the script, you can of course also copy-paste it (and please do read it before using it).
- The script pulls the voting signatures from this public repository: ``https://``. If you don't
trust this process, you can create a file called vote.sig in the same directory that contains the vote script
with the signatures you want to vote on and vote as follows: 

`sudo python3 vote.py yes vote.sig`  
`sudo python3 vote.py no vote.sig`  
`sudo python3 vote.py abstention vote.sig`

- If even that is too much for you, you can vote on an individual signature as follows:

`sudo python3 vote.py yes sig_xxx...`  
`sudo python3 vote.py no sig_xxx..`  
`sudo python3 vote.py abstention sig_xxx..`

## Voting Lifehacks

Voting can take a significant amount of time, due to how Nyzo cycle transactions work.
If you don't want to keep the terminal connection to your sentinel open all the time (or simply
don't trust your internet connection), you can use tmux to run your voting session in the background.
It should come pre-installed on your box, but if not, you can easily install it. Then, type
`tmux`. This will start a detachable session (see the green bar at the bottom of the terminal). Now
start voting as described above. To detach from the voting session, simply type `Ctrl+B`, followed
by `D`. You should now be back in your regular terminal and can log out. To check on your voting
session, reestablish the terminal connection to your sentinel and type `tmux attach`.

## How It Works

- Voting `yes` does the obvious: it signs the corresponding cycle transaction(s) with the private keys from your in-cycle verifiers.
- Voting `no` and `abstention` sends one micronyzo (a negligible amount of money) to the cycle fund, with your vote's fingerprint in the transaction data. 
- The next task will then be to pull the voting data from the chain, sanitize it and display it appropriately.

## Why Voting "No" or "Abstention" Makes Sense

Voting `no` or `abstention` will indeed not change the outcome of the vote (whether the
funds for the proposal in question get released or not). Those votes however still make sense because
they allow the community to gauge voter's interest and opinion. As long as the only possible vote is a
`yes` (signing the transaction), we will never be able to determine whether the non-voters
were uninterested, uninformed, or opposed to the proposal.