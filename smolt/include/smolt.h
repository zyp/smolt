#pragma once

#include <bit>
#include <array>
#include <string_view>
#include <algorithm>
#include <source_location>
#include <concepts>
#include <cstdint>

namespace smolt {
    // Internal utilities.
    namespace util {
        using str_buf = std::array<char, 256>;

        constexpr auto make_str_buf(std::string_view s) {
            str_buf buf {};
            std::copy(s.begin(), s.end(), buf.begin());
            return buf;
        }
    }

    // Metadata containers.
    namespace meta {
        // Format string.
        struct fmt_v0 {
            util::str_buf fmt;
            constexpr fmt_v0(const char* s) : fmt(util::make_str_buf(s)) {}
        };

        // Source location.
        struct loc_v0 {
            util::str_buf filename;
            unsigned line;
        };

        // Format arguments.
        template <typename... T>
        struct args_v0 {};
    }

    // Concepts.
    namespace concepts {
        constexpr void is_meta(meta::fmt_v0) {}
        constexpr void is_meta(meta::loc_v0) {}
        template <typename... T>
        constexpr void is_meta(meta::args_v0<T...>) {}

        template <typename T>
        concept is_meta_type = requires(T t) {
            { is_meta(t) };
        };

        template <typename T>
        concept has_enabled = requires(T t) {
            { t.enabled() } -> std::same_as<bool>;
        };
    }

    // Tag creation.
    struct tag_marker {};
    using tag_id = void (*)(tag_marker);

    template <auto... t>
    void tag(tag_marker) {
        static_assert ((concepts::is_meta_type<decltype(t)> && ...), "Argument is not a valid tag metadata type.");
    }

    // Transports.
    namespace transport {
        struct blackhole {
            void log_tag(uint32_t) const {}
            void log_value(uint32_t) const {}
        };

        struct itm {
            uint8_t channel = 24;

            volatile uint32_t* reg_stim() const {
                return reinterpret_cast<volatile uint32_t*>(0xe0000000);
            }

            volatile uint32_t* reg_ter() const {
                return reinterpret_cast<volatile uint32_t*>(0xe0000e00);
            }

            bool enabled() const {
                return ((reg_ter()[channel / 32] >> (channel % 32)) & 3) == 3;
            }

            // TODO: We could potentially lose a write due to the FIFO being full if preempted between the check and the write.
            // ARM manual suggests using ldrex/strex.

            void log_tag(uint32_t tag) const {
                while((reg_stim()[channel] & 1) == 0);
                reg_stim()[channel] = tag;
            }
            void log_value(uint32_t value) const {
                while((reg_stim()[channel + 1] & 1) == 0);
                reg_stim()[channel + 1] = value;
            }
        };

        template <std::size_t depth>
        struct ringbuffer {
            std::array<uint32_t, depth> data;
            std::size_t write_idx;
            std::size_t tag_idx;

            void log_tag(uint32_t tag) {
                log_value(tag);
                tag_idx = write_idx;
            }

            void log_value(uint32_t value) {
                write_idx = write_idx ? write_idx - 1 : depth - 1;
                data[write_idx] = value;
            }
        };
    }

    // Loggable info.
    namespace info {
        constexpr meta::loc_v0 loc(std::source_location location = std::source_location::current()) {
            return {
                util::make_str_buf(location.file_name()),
                location.line(),
            };
        }
    }

    // Logger.
    template <typename transport_t>
    struct logger {
        transport_t transport;

        void log_tag(tag_id tag) const {
            transport.log_tag(std::bit_cast<uint32_t>(tag));
        }

        template <std::integral T>
        void log_value(T value) const requires (sizeof(T) <= sizeof(uint32_t)) {
            transport.log_value(static_cast<uint32_t>(value));
        }

        void log_value(float value) const {
            transport.log_value(std::bit_cast<uint32_t>(value));
        }

        void log_values() const {}

        template <typename T, typename... U>
        void log_values(T arg, U... args) const {
            log_values(args...);
            log_value(arg);
        }

        template <meta::fmt_v0 str, meta::loc_v0 loc = {}, typename... T>
        void log(T... args) const {
            if constexpr (concepts::has_enabled<transport_t>) {
                if (!transport.enabled()) {
                    return;
                }
            }

            log_values(args...);
            log_tag(tag<str, loc, meta::args_v0<T...>{}>);
        }
    };

    // Do the right thing whether the transport is passed as a reference or a rvalue.
    template <typename transport_t>
    logger(transport_t&&) -> logger<transport_t>;
}
