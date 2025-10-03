# Network
***********
**V3.0.0**

A Mininet-based network topology with an exposed Flask API.

## Composition
The network is basically composed of:
- `One` server-exposing switch: `s0`.
- `4` controlled switches: `[s101, s102, s103, s104]`.
- `One` server host: `hs` exposing a `TCP` client.
- `n` host/router: automatically constructed depending on provided topology file.

## Run arguments:
- `-s`/`--servers`: Server hosts names. E.g: `[h1]` *(a limitation of the current version accepts only `hs` as a server)*.
- `-a`/`--attackers`: Attacker hosts names. E.g: `[h1]`.
- `-uhb`/`--unified-host-bandwidth`: When used, all non-server hosts will have same passed bandwidth. E.g: `3.1`
- `-usb`/`--unified-switch-bandwidth`: When used, all controlled switches will have same passed bandwidth. E.g: `3.1`
- `-mr`/`--manuel-receivers`: Whether to start with a manually configured server.
- `-htf`/`--hosts-topo-file`: When given, the provided JSON file in the `input-data` folder will be used. E.g: `hosts-topology-6hosts`.


## Available topologies:
- `hosts-toplogy-6hosts.json`: `6` hosts connected as following:
    ```
    h1 ---\                             /-- h7
           \-s101 --\        /-- s104 -|
    h2 --\           |- s0 -|           \-- h6
          |- S102 --/        \-- s103-\
    h3 --/                             \--- h4
    ```
- `hosts-topology-99hosts-20_30_30_19.json`: `99` hosts connected as following:
    ```
     h1 ... h20 --\                             /-- h81 ... h99
                   \- s101 --\       /-- s104 -/
                              |- s0 -|          
                   /- S102 --/       \-- s103 -\
    h21 ... h50 --/                             \-- h51 ... h80
    ```

## Commands

**Run only Mininet network**
******

Go to `network` directory and execute:
```shell
sudo python3 EntryPoint.py -mr
```

**With a predifined server**
******

```shell
sudo python3 EntryPoint.py -s [hs] -mr
```

**With a predifined server and attacker**
******

```shell
sudo python3 EntryPoint.py -s [hs] -a [h5] -mr
```

**Using unified BW for hosts**
******

```shell
sudo python3 EntryPoint.py -uhb -mr
```

**Using unified BW for controlled switches**
******

```shell
sudo python3 EntryPoint.py -usb -mr
```

**Open Xterm of a host**
******

```shell
xterm h1
```

**Starting TCP server**
******

URL: http://localhost:5000/reset-tcp-receivers


**Sending TCP flow**
******

From host "h3" to server "hs" for 30 seconds

URL: http://localhost:5000/start-tcp-flow/h3/hs/30000

**Starting attack**
******

From attacker "h5" to server "hs"

Possible attack types:
- ICMP
- TCP
- UDP
- SYN

URL: http://localhost:5000/start-mhddos/h5/hs/TCP

**Stopping attack**
******

From attacker "h5" to server "hs"

URL: http://localhost:5000/stop-mhddos/h5/hs